"""Ozon Seller Bot — MVP для продавцов: сводка, остатки, топ товаров.

Демо-режим включается автоматически, если не заданы OZON_CLIENT_ID и
OZON_API_KEY: данные генерируются детерминированно и помечаются как демо.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import charts
import config
import db as db_module
import ozon_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

db = db_module.Database(config.DB_PATH)

router = Dispatcher()


def _check_access(message: Message) -> bool:
    """В личном демо-боте доступ только у владельца магазина."""
    return not config.ADMIN_IDS or message.from_user.id in config.ADMIN_IDS


async def _refresh() -> tuple[list[dict], bool]:
    products, is_demo = await ozon_api.fetch_products()
    await db.replace_products(products)
    return products, is_demo


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _digest_text(products: list[dict], is_demo: bool) -> str:
    if not products:
        return "Товары не найдены."

    total_revenue = sum(p["revenue"] for p in products)
    total_orders = sum(p["orders"] for p in products)
    low_stock = [p for p in products if p["stock"] <= config.DEFAULT_LOW_STOCK]
    out_of_stock = [p for p in products if p["stock"] == 0]
    top = sorted(products, key=lambda p: -p["revenue"])[:5]

    lines = [
        "📊 <b>Дневная сводка магазина</b>",
        f"Товаров: <b>{len(products)}</b> · заказов: <b>{total_orders}</b> · "
        f"выручка: <b>{_money(total_revenue)} ₽</b>",
        "",
    ]

    if out_of_stock:
        lines.append(f"🔴 <b>Нет в наличии: {len(out_of_stock)}</b>")
        for p in out_of_stock[:3]:
            lines.append(f"  • {_html_escape(p['title'][:40])}")
        lines.append("")

    if low_stock:
        lines.append(f"🟡 <b>Мало на складе (≤{config.DEFAULT_LOW_STOCK}): {len(low_stock)}</b>")
        for p in low_stock[:5]:
            lines.append(f"  • {_html_escape(p['title'][:40])} — {p['stock']} шт.")
        lines.append("")

    lines.append("🏆 <b>Топ-5 по выручке:</b>")
    for i, p in enumerate(top, 1):
        lines.append(
            f"{i}. {_html_escape(p['title'][:35])} — "
            f"<b>{_money(p['revenue'])} ₽</b> ({p['orders']} зак.)"
        )

    demo = "\n⚠️ <i>Демо-режим: данные сгенерированы, ключи Seller API не заданы.</i>" if is_demo else ""
    return "\n".join(lines) + demo


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not _check_access(message):
        return
    await message.answer(
        "👋 <b>Ozon Seller Bot</b> — сводка магазина в Telegram.\n\n"
        "/summary — дневная сводка: выручка, заказы, остатки\n"
        "/stock — контроль остатков: что заканчивается\n"
        "/top — топ товаров по выручке\n"
        "/chart — график выручки за 14 дней\n"
        "/alerts — автоалерты: сводка по расписанию и «товар закончился»\n"
        "/refresh — обновить данные из API\n\n"
        "Данные обновляются при каждом /refresh и перед сводкой."
    )


@router.message(Command("summary"))
async def cmd_summary(message: Message) -> None:
    if not _check_access(message):
        return
    products, is_demo = await _refresh()
    await message.answer(_digest_text(products, is_demo))


@router.message(Command("stock"))
async def cmd_stock(message: Message) -> None:
    if not _check_access(message):
        return
    products, is_demo = await _refresh()
    low = sorted(
        [p for p in products if p["stock"] <= config.DEFAULT_LOW_STOCK],
        key=lambda p: p["stock"],
    )
    if not low:
        await message.answer("✅ Все товары в достатке.")
        return
    lines = [f"📦 <b>Остатки ≤ {config.DEFAULT_LOW_STOCK} шт.:</b>\n"]
    for p in low:
        emoji = "🔴" if p["stock"] == 0 else "🟡"
        lines.append(f"{emoji} {_html_escape(p['title'][:40])} — <b>{p['stock']} шт.</b>")
    if is_demo:
        lines.append("\n⚠️ <i>Демо-режим.</i>")
    await message.answer("\n".join(lines))


@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
    if not _check_access(message):
        return
    products, is_demo = await _refresh()
    top = sorted(products, key=lambda p: -p["revenue"])[:10]
    lines = ["🏆 <b>Топ-10 по выручке:</b>\n"]
    for i, p in enumerate(top, 1):
        lines.append(
            f"{i}. {_html_escape(p['title'][:38])}\n"
            f"    {_money(p['revenue'])} ₽ · {p['orders']} заказов · ★ {p['rating']}"
        )
    if is_demo:
        lines.append("\n⚠️ <i>Демо-режим.</i>")
    await message.answer("\n".join(lines))


@router.message(Command("refresh"))
async def cmd_refresh(message: Message) -> None:
    if not _check_access(message):
        return
    status = await message.answer("🔄 Обновляю данные из API…")
    try:
        products, is_demo = await _refresh()
        await status.edit_text(
            f"✅ Обновлено товаров: <b>{len(products)}</b>"
            + ("\n⚠️ <i>Демо-режим: ключи Seller API не заданы.</i>" if is_demo else "")
        )
    except Exception as exc:  # noqa: BLE001 — MVP: показываем ошибку пользователю
        logger.exception("Ошибка обновления")
        await status.edit_text(f"⚠️ Ошибка обновления: {exc}")


@router.message(Command("chart"))
async def cmd_chart(message: Message) -> None:
    """График выручки за 14 дней (в демо-режиме — детерминированная динамика)."""
    if not _check_access(message):
        return
    status = await message.answer("📊 Строю график…")
    series = ozon_api.demo_revenue_history(14)
    photo = charts.render_revenue(series, is_demo=True)
    await status.delete()
    await message.answer_photo(
        photo,
        caption=(
            "📊 <b>Динамика выручки за 14 дней.</b>\n"
            "Пик недели подсвечен. В демо-режиме — модельные данные; "
            "с ключами Seller API здесь будет фактическая выручка магазина."
        ),
    )


@router.message(Command("alerts"))
async def cmd_alerts(message: Message) -> None:
    """Подписка/отписка на автоматические алерты: сводка по расписанию + «товар закончился»."""
    if not _check_access(message):
        return
    await db.toggle_digest(message.from_user.id)
    on = await db.digest_enabled(message.from_user.id)
    state = "включены" if on else "выключены"
    hours = ", ".join(str(h) for h in config.STOCK_CHECK_HOURS)
    await message.answer(
        f"{'🔔' if on else '🔕'} Автоалерты <b>{state}</b>.\n"
        f"• Дневная сводка — ежедневно в {config.DIGEST_HOUR}:00\n"
        f"• «Товар закончился» — проверки в {hours}"
    )


async def send_digest(bot: Bot) -> None:
    """Плановая дневная сводка всем, у кого алерты включены."""
    products, is_demo = await _refresh()
    text = f"⏰ <b>Автосводка {config.DIGEST_HOUR}:00</b>\n\n" + _digest_text(products, is_demo)
    for chat_id in await db.digest_subscribers():
        try:
            await bot.send_message(chat_id, text)
        except Exception:  # noqa: BLE001 — один недоступный чат не срывает рассылку
            logger.warning("Не доставили сводку в %s", chat_id)


async def check_stockouts(bot: Bot) -> None:
    """Алерты «товар закончился»: остаток стал нулевым с прошлой проверки."""
    products, is_demo = await _refresh()
    current = {p["offer_id"] for p in products if p["stock"] == 0}
    previous = await db.prev_stockouts()
    new = current - previous
    await db.save_stockouts(current)
    if not new or is_demo:
        return
    titles = {p["offer_id"]: p["title"] for p in products}
    lines = ["🚨 <b>Закончился товар:</b>"] + [
        f"• {_html_escape(titles.get(oid, oid)[:45])}" for oid in list(new)[:5]
    ]
    for chat_id in await db.digest_subscribers():
        try:
            await bot.send_message(chat_id, "\n".join(lines))
        except Exception:  # noqa: BLE001
            logger.warning("Не доставили алерт в %s", chat_id)


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit(
            "❌ OZON_SELLER_BOT_TOKEN не задан. Скопируйте .env.example в .env "
            "и впишите токен от @BotFather."
        )
    await db.init()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Плановые задачи: дневная сводка + проверки обнуления остатков
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_digest, CronTrigger(hour=config.DIGEST_HOUR, minute=0), args=[bot])
    for hour in config.STOCK_CHECK_HOURS:
        scheduler.add_job(check_stockouts, CronTrigger(hour=hour, minute=30), args=[bot])
    scheduler.start()

    logger.info("Запуск бота (demo=%s)", config.DEMO_MODE)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

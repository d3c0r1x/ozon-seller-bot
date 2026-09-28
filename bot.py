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


_STATUS_RU = {
    "awaiting_packaging": "🕓 Ждёт упаковки",
    "awaiting_deliver": "🕓 Ждёт отгрузки",
    "arbitration": "⚖️ Арбитраж",
    "delivering": "🚚 В доставке",
    "delivered": "✅ Доставлен",
    "cancelled": "❌ Отменён",
}


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    """FBS-отправления за сутки: статусы, суммы, алерт о новых."""
    if not _check_access(message):
        return
    status = await message.answer("📦 Загружаю отправления…")
    try:
        orders, is_demo = await ozon_api.fetch_fbs_orders(hours=24)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка загрузки отправлений")
        await status.edit_text(f"⚠️ Ошибка: {exc}")
        return

    if not orders:
        await status.edit_text("За сутки отправлений нет.")
        return

    prev_numbers = await db.prev_order_numbers()
    new_numbers = [o for o in orders if o["number"] not in prev_numbers]
    await db.save_order_numbers({o["number"] for o in orders})

    lines = [f"📦 <b>FBS за 24 ч:</b> {len(orders)} отправлений\n"]
    new_first = new_numbers + [o for o in orders if o not in new_numbers]
    for o in new_first[:8]:
        ru = _STATUS_RU.get(o["status"], o["status"])
        badge = " 🆕" if o in new_numbers else ""
        lines.append(
            f"{ru}{badge} — <b>{_money(o['price'])} ₽</b>\n"
            f"    <code>{_html_escape(o['number'])}</code> · {o['created_at']}"
        )
    if is_demo:
        lines.append("\n⚠️ <i>Демо-режим.</i>")
    await status.edit_text("\n".join(lines))



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
        "/orders — FBS-отправления за сутки со статусами\n"
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
        f"• Проверки в {hours}:30: «товар закончился», падение цены ≥{config.PRICE_DROP_PCT}%, "
        f"рейтинг <{config.RATING_ALERT_BELOW}"
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
    """Проверка после изменений: stockout'ы, падение цены, низкий рейтинг."""
    products, is_demo = await _refresh()
    if is_demo:
        # В демо-режиме данные не меняются — алертов нет, но снапшоты поддерживаем.
        await db.save_snapshots(products)
        return

    # 1) «товар закончился»: новые обнуления остатка
    current_out = {p["offer_id"] for p in products if p["stock"] == 0}
    new_out = current_out - await db.prev_stockouts()
    await db.save_stockouts(current_out)

    # 2) падение цены и низкий рейтинг — сравнение со снапшотом прошлой проверки
    prev = await db.prev_snapshots()
    price_drops: list[tuple[str, str, float]] = []
    low_ratings: list[tuple[str, str, float]] = []
    for p in products:
        old = prev.get(p["offer_id"])
        if old:
            old_price, old_rating = old
            if old_price > 0 and p["price"] < old_price * (100 - config.PRICE_DROP_PCT) / 100:
                pct = (1 - p["price"] / old_price) * 100
                price_drops.append((p["offer_id"], p["title"], pct))
            if 0 < p["rating"] < config.RATING_ALERT_BELOW and old_rating >= config.RATING_ALERT_BELOW:
                low_ratings.append((p["offer_id"], p["title"], p["rating"]))
        elif p["rating"] and p["rating"] < config.RATING_ALERT_BELOW:
            low_ratings.append((p["offer_id"], p["title"], p["rating"]))
    await db.save_snapshots(products)

    # 3) доставка: одна сводка алертов вместо трёх сообщений
    if not (new_out or price_drops or low_ratings):
        return
    titles = {p["offer_id"]: p["title"] for p in products}
    lines: list[str] = ["🚨 <b>Алерты магазина:</b>"]
    if new_out:
        lines.append("\n<b>Закончился товар:</b>")
        lines += [f"• {_html_escape(titles.get(oid, oid)[:45])}" for oid in list(new_out)[:5]]
    if price_drops:
        lines.append(f"\n<b>Цена упала ≥ {config.PRICE_DROP_PCT}%:</b>")
        lines += [
            f"• {_html_escape(t[:40])} — −{pct:.0f}%"
            for _, t, pct in price_drops[:5]
        ]
    if low_ratings:
        lines.append(f"\n<b>Рейтинг ниже {config.RATING_ALERT_BELOW}:</b>")
        lines += [
            f"• {_html_escape(t[:40])} — ★ {r}" for _, t, r in low_ratings[:5]
        ]
    for chat_id in await db.digest_subscribers():
        try:
            await bot.send_message(chat_id, "\n".join(lines))
        except Exception:  # noqa: BLE001
            logger.warning("Не доставили алерты в %s", chat_id)


async def check_new_orders(bot: Bot) -> None:
    """Плановая проверка: новые FBS-отправления с прошлого раза -> алерт."""
    try:
        orders, is_demo = await ozon_api.fetch_fbs_orders(hours=config.ORDERS_LOOKBACK_HOURS)
    except Exception:  # noqa: BLE001 — планировщик не должен падать
        logger.exception("Не получили FBS-отправления")
        return
    if is_demo or not orders:
        return
    prev = await db.prev_order_numbers()
    new = [o for o in orders if o["number"] not in prev]
    if not new:
        return
    await db.save_order_numbers({o["number"] for o in orders})
    total = sum(o["price"] for o in new)
    lines = [
        f"📬 <b>Новые FBS-отправления: {len(new)}</b> на {_money(total)} ₽",
        "",
    ]
    for o in new[:5]:
        ru = _STATUS_RU.get(o["status"], o["status"])
        lines.append(f"{ru} — {_money(o['price'])} ₽ · <code>{_html_escape(o['number'])}</code>")
    if len(new) > 5:
        lines.append(f"…и ещё {len(new) - 5}")
    for chat_id in await db.digest_subscribers():
        try:
            await bot.send_message(chat_id, "\n".join(lines))
        except Exception:  # noqa: BLE001
            logger.warning("Не доставили алерт о заказах в %s", chat_id)


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

    # Плановые задачи: дневная сводка + проверки (остатки, цены, рейтинги, новые FBS)
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_digest, CronTrigger(hour=config.DIGEST_HOUR, minute=0), args=[bot])
    for hour in config.STOCK_CHECK_HOURS:
        scheduler.add_job(check_stockouts, CronTrigger(hour=hour, minute=30), args=[bot])
    if config.ORDERS_CHECK_ENABLED:
        scheduler.add_job(check_new_orders, CronTrigger(minute=config.ORDERS_CHECK_MINUTE), args=[bot])
    scheduler.start()

    logger.info("Запуск бота (demo=%s)", config.DEMO_MODE)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

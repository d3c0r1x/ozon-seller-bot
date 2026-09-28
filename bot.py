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
    logger.info("Запуск бота (demo=%s)", config.DEMO_MODE)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

"""Хранилище состояния бота (aiosqlite)."""

from __future__ import annotations

from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    offer_id TEXT PRIMARY KEY,
                    title TEXT,
                    price REAL,
                    old_price REAL,
                    stock INTEGER,
                    orders INTEGER,
                    revenue REAL,
                    rating REAL
                );

                CREATE TABLE IF NOT EXISTS digest_subscribers (
                    chat_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS stockouts (
                    offer_id TEXT PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    offer_id TEXT PRIMARY KEY,
                    price REAL,
                    rating REAL
                );
                """
            )

    async def replace_products(self, products: list[dict[str, Any]]) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM products")
            await db.executemany(
                """
                INSERT INTO products
                (offer_id, title, price, old_price, stock, orders, revenue, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        p["offer_id"], p["title"], p["price"], p["old_price"],
                        p["stock"], p["orders"], p["revenue"], p["rating"],
                    )
                    for p in products
                ],
            )
            await db.commit()

    # --- автоалерты ---

    async def toggle_digest(self, chat_id: int) -> None:
        """Включает/выключает автоалерты для чата (по умолчанию — включены при первом /alerts)."""
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute(
                    "SELECT enabled FROM digest_subscribers WHERE chat_id = ?", (chat_id,)
                )
            ).fetchone()
            new_state = 0 if (row and row[0]) else 1
            await db.execute(
                """
                INSERT INTO digest_subscribers (chat_id, enabled) VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled
                """,
                (chat_id, new_state),
            )
            await db.commit()

    async def digest_enabled(self, chat_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            row = await (
                await db.execute(
                    "SELECT enabled FROM digest_subscribers WHERE chat_id = ?", (chat_id,)
                )
            ).fetchone()
        return bool(row and row[0])

    async def digest_subscribers(self) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            rows = await (
                await db.execute(
                    "SELECT chat_id FROM digest_subscribers WHERE enabled = 1"
                )
            ).fetchall()
        return [r[0] for r in rows]

    async def prev_stockouts(self) -> set[str]:
        """Набор offer_id, обнулившихся на прошлой проверке (для поиска новых)."""
        async with aiosqlite.connect(self.path) as db:
            rows = await (await db.execute("SELECT offer_id FROM stockouts")).fetchall()
        return {r[0] for r in rows}

    async def save_stockouts(self, offer_ids: set[str]) -> None:
        """Полная замена набора обнулившихся товаров на текущий."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM stockouts")
            await db.executemany(
                "INSERT INTO stockouts (offer_id) VALUES (?)",
                [(oid,) for oid in offer_ids],
            )
            await db.commit()

    # --- снапшоты цен/рейтингов для алертов ---

    async def prev_snapshots(self) -> dict[str, tuple[float, float]]:
        """{offer_id: (price, rating)} с прошлой проверки."""
        async with aiosqlite.connect(self.path) as db:
            rows = await (
                await db.execute("SELECT offer_id, price, rating FROM snapshots")
            ).fetchall()
        return {r[0]: (r[1], r[2]) for r in rows}

    async def save_snapshots(self, products: list[dict[str, Any]]) -> None:
        """Полная замена снапшотов цен/рейтингов текущими товарами."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM snapshots")
            await db.executemany(
                "INSERT INTO snapshots (offer_id, price, rating) VALUES (?, ?, ?)",
                [(p["offer_id"], p["price"], p["rating"]) for p in products],
            )
            await db.commit()

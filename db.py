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
                )
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

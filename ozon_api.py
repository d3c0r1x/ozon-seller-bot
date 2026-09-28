"""Клиент Seller API Ozon.

Реальный режим: POST /v3/posting/fbs/list + /v3/product/list (упрощённая
агрегация). Демо-режим (нет ключей): детерминированный набор данных —
одинаковый при каждом запуске, чтобы демо и тесты были воспроизводимыми.
"""

from __future__ import annotations

import random
from typing import Any

import httpx

import config

_API_URL = "https://api-seller.ozon.ru"


async def fetch_products() -> tuple[list[dict[str, Any]], bool]:
    """Возвращает (товары, is_demo). В демо-режиме данные генерируются локально."""
    if config.DEMO_MODE:
        return _demo_products(), True

    async with httpx.AsyncClient(timeout=30) as client:
        headers = {
            "Client-Id": config.OZON_CLIENT_ID,
            "Api-Key": config.OZON_API_KEY,
            "Content-Type": "application/json",
        }
        # 1) список товаров
        resp = await client.post(f"{_API_URL}/v3/product/list", json={}, headers=headers)
        resp.raise_for_status()
        result = resp.json().get("result", {})
        items = result.get("items", [])

        products: list[dict[str, Any]] = []
        for it in items[:50]:
            offer_id = str(it.get("offer_id", it.get("product_id", "")))
            # 2) карточка с ценами и остатками
            info = await client.post(
                f"{_API_URL}/v4/product/info/prices",
                json={"filter": {"offer_id": [offer_id]}},
                headers=headers,
            )
            info.raise_for_status()
            prices = (info.json().get("items") or [{}])[0]
            price = float(prices.get("price", {}).get("price") or 0)
            old_price = float(prices.get("price", {}).get("old_price") or 0)
            stock = int(prices.get("stock", 0) or 0)

            products.append(
                {
                    "offer_id": offer_id,
                    "title": str(it.get("name", offer_id))[:80],
                    "price": price,
                    "old_price": old_price,
                    "stock": stock,
                    "orders": 0,      # продажи — из аналитики, тут упрощение MVP
                    "revenue": 0.0,
                    "rating": 0.0,
                }
            )
        return products, False


# --- демо-данные ---

_DEMO_TITLES = [
    "Чехол для iPhone 15 Pro, чёрный",
    "Наушники TWS Pro 5, белые",
    "Кабель USB-C 2м, оплётка",
    "Держатель для телефона в авто",
    "Зарядное устройство 65W GaN",
    "Стекло защитное 9H, 2 шт",
    "Power bank 20000 mAh",
    "Подставка для ноутбука, алюминий",
    "Мышь беспроводная, тихие клики",
    "Коврик для мыши XXL",
    "Переходник USB-C → HDMI",
    "Микрофон петличный USB-C",
]


def demo_revenue_history(days: int = 14) -> list[float]:
    """Детерминированная дневная выручка за последние N дней (для /chart в демо)."""
    rng = random.Random(42)
    base = sum(p["revenue"] for p in _demo_products()) / days
    series = []
    for i in range(days):
        # недельная волна: выходные выше + шум
        factor = 1.25 if (i % 7) in (5, 6) else 1.0
        series.append(round(base * factor * rng.uniform(0.75, 1.25), 2))
    return series


def _demo_products() -> list[dict[str, Any]]:
    rng = random.Random(42)  # фиксируем seed: демо воспроизводимо
    products = []
    for i, title in enumerate(_DEMO_TITLES):
        price = rng.choice([290, 450, 790, 990, 1290, 1590, 2290])
        orders = rng.randint(3, 120)
        products.append(
            {
                "offer_id": f"SKU-{1000 + i}",
                "title": title,
                "price": float(price),
                "old_price": round(price * rng.choice([1.15, 1.25, 1.4]), 2),
                "stock": rng.choice([0, 2, 5, 12, 25, 40, 120]),
                "orders": orders,
                "revenue": round(price * orders, 2),
                "rating": rng.choice([4.5, 4.6, 4.7, 4.8, 4.9, 5.0]),
            }
        )
    return products

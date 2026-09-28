# Ozon Seller Bot

[![CI](https://github.com/d3c0r1x/ozon-seller-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/d3c0r1x/ozon-seller-bot/actions/workflows/ci.yml)

MVP-бот для продавцов Ozon: сводка магазина в Telegram — выручка и заказы, контроль остатков, топ товаров. Работает через Seller API Ozon; **без ключей включается демо-режим** с детерминированными данными, чтобы показать функционал без доступа к магазину.

## Возможности

- **/summary** — дневная сводка: товаров, заказов, выручка, проблемные остатки, топ-5 по выручке;
- **/stock** — контроль остатков: 🔴 нет в наличии, 🟡 мало на складе (порог настраивается);
- **/top** — топ-10 товаров по выручке с рейтингами;
- **/refresh** — принудительное обновление данных из API;
- **/alerts** — автоалерты: дневная сводка по расписанию (9:00 МСК) и мгновенный алерт «🚨 товар закончился» при обнулении остатка (проверки в 9:30 и 21:30);
- **демо-режим**: нет ключей Seller API → данные генерируются детерминированно (12 товаров, seed=42), помечаются как демо; тесты и демо воспроизводимы;
- доступ только у владельца (`ADMIN_IDS`): личный кабинет магазина, а не публичный бот.

## Запуск

```bash
pip install -r requirements.txt
copy .env.example .env   # впишите OZON_SELLER_BOT_TOKEN и ADMIN_IDS
python bot.py
```

Для реального магазина добавьте в `.env`:

```
OZON_CLIENT_ID=...
OZON_API_KEY=...
```

(https://seller.ozon.ru → Настройки → API-ключи). Без них бот честно скажет, что работает в демо-режиме.

## Архитектура

- `bot.py` — aiogram 3: команды, доступ по `ADMIN_IDS`, тексты сводок;
- `ozon_api.py` — клиент Seller API (`/v3/product/list`, `/v4/product/info/prices`) + детерминированный демо-слой;
- `db.py` — кэш товаров в SQLite (aiosqlite);
- `config.py` — переменные окружения через `python-dotenv`.

## Roadmap MVP

- [x] плановая дневная сводка по расписанию (APScheduler, AsyncIOScheduler);
- [x] алерт «товар закончился»: сравнение с прошлой проверкой, только новые stockout'ы;
- [ ] алерты: цена упала, рейтинг ниже порога;
- [ ] динамика выручки по дням (график);
- [ ] FBS-заказы: новые отправления и статусы.

## 🇬🇧 English

**Ozon Seller Bot** — an MVP Telegram bot for Ozon marketplace sellers: daily store summary (revenue, orders, stock alerts, top products), low-stock control and instant "out of stock" alerts. Built on the Ozon Seller API with a deterministic demo mode (no keys required — reproducible demo data, covered by CI). Personal-store access control via `ADMIN_IDS`.

## Лицензия

MIT — см. [LICENSE](LICENSE).

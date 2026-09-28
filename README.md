# Ozon Seller Bot

> **Прикладной MVP-проект.** Я использовал его как практическую автоматизацию для продавца Ozon: получение показателей магазина, контроль остатков, FBS-заказы и плановые уведомления в Telegram.
>
> Это не главный флагман портфолио, но проект показывает работу с реальным marketplace API и бизнес-ориентированной логикой.

[![CI](https://github.com/d3c0r1x/ozon-seller-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/d3c0r1x/ozon-seller-bot/actions/workflows/ci.yml)

## Что делает

Приватный Telegram-бот для владельца магазина Ozon.

Команды:

| Команда | Что показывает |
|---|---|
| `/summary` | товары, заказы, выручка, проблемные остатки, top-5 |
| `/stock` | out-of-stock и low-stock |
| `/top` | топ-10 товаров по выручке |
| `/chart` | график выручки за 14 дней |
| `/orders` | FBS-отправления за сутки |
| `/refresh` | принудительно обновить данные |
| `/alerts` | состояние автоалертов |

Бот работает только для пользователей из `ADMIN_IDS`.

## Demo mode

Без Seller API credentials бот не падает.

Он включает детерминированный demo mode:

- 12 условных товаров;
- воспроизводимые значения;
- те же бизнес-сценарии;
- можно показать проект без доступа к реальному магазину.

## Архитектура

```
Telegram
   ↓
bot.py
   ├── Ozon Seller API
   ├── demo provider
   ├── SQLite cache
   ├── charts
   └── APScheduler alerts
```

## Структура

```
bot.py          # Telegram handlers / menu / scheduled jobs
ozon_api.py     # Ozon Seller API + deterministic demo
db.py           # SQLite cache
charts.py       # matplotlib charts
config.py       # environment configuration
```

## Запуск

Требования:

- Python 3.11+;
- Telegram Bot Token.

Установка:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Создать `.env` на основе [.env.example](.env.example):

```
OZON_SELLER_BOT_TOKEN=123456:ABC...
ADMIN_IDS=123456789
```

Запуск:

```bash
python bot.py
```

Без `OZON_CLIENT_ID` и `OZON_API_KEY` запускается demo mode.

## Подключение реального магазина

В Ozon Seller API создаются credentials, после чего:

```
OZON_CLIENT_ID=...
OZON_API_KEY=...
```

После этого `ozon_api.py` обращается к Seller API, а остальная бизнес-логика остаётся той же.

## Плановые проверки

Система использует scheduler.

В проекте реализованы:

- дневная сводка;
- проверки out-of-stock;
- падение цены ≥ 10%;
- рейтинг ниже порога;
- регулярная проверка FBS-отправлений.

## Графики

`/chart` строит PNG-график динамики выручки за 14 дней.

Вся визуализация создаётся из кэшированных данных и не требует отдельного frontend.

## Тестирование

CI запускает тесты и deterministic demo path.

Для локальной проверки:

```bash
pytest -q
```

## Ограничения

- MVP рассчитан на личный магазин;
- API Ozon может меняться;
- для production лучше разделить background jobs и Telegram process;
- SQLite подходит для этого масштаба, но для multi-tenant сервиса потребовалась бы другая архитектура.

## AI-assisted development

AI использовался для чернового кода, тестовых идей и рутинных частей.

Архитектуру, интеграцию API, debugging и итоговое поведение проекта я проверял сам.

## Лицензия

MIT.

import os

from dotenv import load_dotenv

load_dotenv()

# Токен бота от @BotFather
BOT_TOKEN = os.getenv("OZON_SELLER_BOT_TOKEN", "")

# Telegram ID владельца магазина — только он пользуется ботом
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",") if x.strip().isdigit()
}

# Ключи Seller API Ozon (https://seller.ozon.ru → Настройки → API-ключи)
OZON_CLIENT_ID = os.getenv("OZON_CLIENT_ID", "")
OZON_API_KEY = os.getenv("OZON_API_KEY", "")

# Без ключей бот работает в демо-режиме: данные генерируются детерминированно,
# помечаются как демо и служат для показа функционала (портфолио/разработка).
DEMO_MODE = not (OZON_CLIENT_ID and OZON_API_KEY)

# Порог остатка по умолчанию: ниже — товар попадает в алерты
DEFAULT_LOW_STOCK = 10

# Час дневной сводки (локальное время)
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "9"))

# Часы проверок «товар закончился» (после сводки и вечером)
STOCK_CHECK_HOURS = [9, 21]

# Порог падения цены, % от прошлой проверки: больше — алерт
PRICE_DROP_PCT = int(os.getenv("PRICE_DROP_PCT", "10"))

# Рейтинг ниже этого значения — алерт
RATING_ALERT_BELOW = float(os.getenv("RATING_ALERT_BELOW", "4.5"))

# База
DB_PATH = os.getenv("OZON_SELLER_DB", "seller_bot.db")

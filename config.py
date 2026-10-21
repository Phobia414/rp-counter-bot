import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RP_OWNER_ID = int(os.getenv("RP_OWNER_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "rp_bot.db")

# Оставляем настройку часового пояса из Шага 1
TZ = ZoneInfo(os.getenv("TZ", "Europe/Moscow"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")
if RP_OWNER_ID == 0:
    raise RuntimeError("RP_OWNER_ID не найден в .env")
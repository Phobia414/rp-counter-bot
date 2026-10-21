import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram.types import BotCommand, BotCommandScopeChat

from bot_instance import bot, dp
from config import RP_OWNER_ID
from db import init_db
from logger import setup_logging, get_logger

import handlers  # noqa: F401  — регистрирует все хэндлеры
from handlers.rp_stats import cleanup_rp_stats

log = get_logger(__name__)


async def set_bot_commands():
    commands = [
        BotCommand(command="rp_on",         description="Включить счётчик"),
        BotCommand(command="rp_off",        description="Выключить счётчик"),
        BotCommand(command="top_rp",        description="Топ по отыгрышу (сегодня)"),
        BotCommand(command="top_rp_week",   description="Топ по отыгрышу (7 дней)"),
        BotCommand(command="top_off",       description="Топ по оффтопу (сегодня)"),
        BotCommand(command="top_off_week",  description="Топ по оффтопу (7 дней)"),
        BotCommand(command="rp_list",       description="Список участников"),
        BotCommand(command="rp_me",         description="Личная статистика"),
    ]
    try:
        await bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=RP_OWNER_ID)
        )
        log.info(f"✅ Команды установлены для владельца (ID {RP_OWNER_ID})")
    except Exception as e:
        log.error(f"set_my_commands error: {e}")


async def main():
    setup_logging()
    log.info("=== RP BOT ЗАПУСКАЕТСЯ ===")

    await init_db()
    log.info("✅ База данных готова")

    await set_bot_commands()

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        cleanup_rp_stats,
        CronTrigger(hour=4, minute=0),
        id="cleanup_rp_stats",
        name="Очистка RP-статистики",
    )
    scheduler.start()
    log.info("✅ Планировщик запущен")

    log.info(f"👑 Владелец бота (ID): {RP_OWNER_ID}")
    log.info("=== БОТ ЗАПУЩЕН ===")

    try:
        # НОВОЕ: Очищаем накопившиеся старые сообщения (защита от спама)
        log.info("🧹 Очистка очереди старых сообщений...")
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем получение новых сообщений
        await dp.start_polling(bot)
    finally:
        log.info("=== ОСТАНОВКА БОТА ===")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Бот остановлен")
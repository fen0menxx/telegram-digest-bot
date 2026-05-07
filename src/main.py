"""
Точка входа Telegram Digest Bot.

Запуск: python -m src.main

Режимы:
- run: Запуск бота (по умолчанию)
- auth: Авторизация Telethon userbot
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="DEBUG",
)
logger.add(
    settings.DATA_DIR / "bot.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
)


async def run_bot() -> None:
    """Запуск бота."""
    logger.info("=" * 50)
    logger.info("TELEGRAM DIGEST BOT")
    logger.info("=" * 50)
    
    # Проверяем настройки
    errors = settings.validate()
    if errors:
        for error in errors:
            logger.error(error)
        logger.error("Заполните .env файл и перезапустите бота")
        return
    
    # Инициализация БД
    from src.storage.database import init_db
    await init_db()
    
    # Инициализация Telethon
    from src.userbot.client import init_client
    await init_client()
    
    # Создаём бота
    from src.bot.bot import create_bot, create_dispatcher
    bot = create_bot()
    dp = create_dispatcher()
    
    # Настраиваем планировщик
    from src.scheduler.tasks import set_bot, start_scheduler, catch_up_digests
    set_bot(bot)
    start_scheduler()
    
    # Catch-up: проверяем пропущенные дайджесты
    await catch_up_digests()
    
    # Запускаем бота
    logger.info(f"Бот запущен. Owner ID: {settings.OWNER_ID}")
    logger.info("Нажмите Ctrl+C для остановки")
    
    try:
        await dp.start_polling(bot)
    finally:
        from src.scheduler.tasks import stop_scheduler
        from src.userbot.client import disconnect_client
        
        stop_scheduler()
        await disconnect_client()
        await bot.session.close()


async def run_auth() -> None:
    """Авторизация Telethon userbot."""
    logger.info("=" * 50)
    logger.info("АВТОРИЗАЦИЯ TELETHON")
    logger.info("=" * 50)
    
    from src.userbot.client import init_client, disconnect_client
    
    try:
        await init_client()
        logger.success("Авторизация успешна!")
    finally:
        await disconnect_client()


def main() -> None:
    """Точка входа."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    
    if mode == "auth":
        asyncio.run(run_auth())
    else:
        asyncio.run(run_bot())


if __name__ == "__main__":
    main()





























0
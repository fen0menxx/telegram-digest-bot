"""
Создание и настройка бота aiogram.
"""

import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings


def create_bot() -> Bot:
    """Создать экземпляр бота."""
    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Создать диспетчер и подключить роутеры."""
    from src.bot.handlers.start import router as start_router
    from src.bot.handlers.setup import router as setup_router
    from src.bot.handlers.settings import router as settings_router
    from src.bot.handlers.digest import router as digest_router
    from src.bot.middleware import OwnerMiddleware
    
    dp = Dispatcher()
    
    # Middleware для проверки владельца
    dp.message.middleware(OwnerMiddleware())
    dp.callback_query.middleware(OwnerMiddleware())
    
    # Подключаем роутеры
    dp.include_router(start_router)
    dp.include_router(setup_router)
    dp.include_router(settings_router)
    dp.include_router(digest_router)
    
    return dp






























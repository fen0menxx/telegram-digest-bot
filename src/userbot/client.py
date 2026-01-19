"""
Клиент Telethon для работы с Telegram API.

Userbot нужен для:
- Сканирования каналов пользователя
- Получения сообщений из каналов
"""

import sys
from pathlib import Path

from telethon import TelegramClient
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings

# Глобальный клиент
client: TelegramClient | None = None


async def init_client() -> TelegramClient:
    """Инициализация и авторизация Telethon клиента."""
    global client
    
    logger.info("Инициализация Telethon клиента...")
    
    client = TelegramClient(
        str(settings.SESSION_PATH),
        settings.API_ID,
        settings.API_HASH,
    )
    
    await client.start()
    
    me = await client.get_me()
    logger.success(f"Авторизован как: {me.first_name} (@{me.username})")
    
    return client


async def get_client() -> TelegramClient:
    """Получить клиент, инициализировать если нужно."""
    global client
    
    if client is None:
        return await init_client()
    
    return client


async def disconnect_client() -> None:
    """Отключение клиента."""
    global client
    
    if client is not None:
        await client.disconnect()
        client = None
        logger.info("Telethon клиент отключён")


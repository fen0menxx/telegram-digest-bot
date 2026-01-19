"""
Сканирование каналов и групп пользователя.

Получает список всех каналов и групп, на которые подписан пользователь.
"""

import sys
from pathlib import Path
from dataclasses import dataclass

from telethon.tl.types import Channel, Chat
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.userbot.client import get_client


@dataclass
class ChannelInfo:
    """Информация о канале/группе."""
    id: int
    title: str
    username: str | None
    is_channel: bool  # True = канал, False = группа


async def scan_user_channels() -> list[ChannelInfo]:
    """
    Сканирует все каналы и группы пользователя.
    
    Returns:
        Список ChannelInfo с информацией о каналах
    """
    client = await get_client()
    
    channels = []
    
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        
        # Только каналы и группы (не личные чаты)
        if isinstance(entity, Channel):
            channels.append(ChannelInfo(
                id=entity.id,
                title=entity.title,
                username=entity.username,
                is_channel=entity.broadcast,  # broadcast = канал, иначе супергруппа
            ))
        elif isinstance(entity, Chat):
            # Обычные группы (не супергруппы)
            channels.append(ChannelInfo(
                id=entity.id,
                title=entity.title,
                username=None,
                is_channel=False,
            ))
    
    logger.info(f"Найдено {len(channels)} каналов и групп")
    
    return channels


"""
Получение сообщений из каналов.

Загружает сообщения за указанный период для генерации дайджеста.
"""

import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from telethon.errors import ChannelPrivateError, ChannelInvalidError
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.userbot.client import get_client


@dataclass
class MessageInfo:
    """Информация о сообщении."""
    channel_id: int
    channel_title: str
    message_id: int
    text: str
    date: datetime
    views: int | None
    link: str


async def get_messages_from_channels(
    channels: list[tuple[int, str, str | None]],
    since: datetime,
    until: datetime,
    limit_per_channel: int = 50,
) -> list[MessageInfo]:
    """
    Получает сообщения из списка каналов за период.
    
    Args:
        channels: Список (channel_id, title, username)
        since: Начало периода
        until: Конец периода
        limit_per_channel: Максимум сообщений с канала
    
    Returns:
        Список MessageInfo
    """
    client = await get_client()
    
    all_messages = []
    channels_with_messages = 0
    
    for channel_id, title, username in channels:
        try:
            # Получаем entity канала
            try:
                entity = await client.get_entity(channel_id)
            except ValueError:
                # Если не удалось по ID, пробуем по username
                if username:
                    entity = await client.get_entity(username)
                else:
                    logger.warning(f"Не удалось найти канал {title} (ID: {channel_id})")
                    continue
            
            messages = []
            
            async for msg in client.iter_messages(
                entity,
                limit=limit_per_channel,
                offset_date=until,
            ):
                # Пропускаем сообщения вне периода
                if msg.date.replace(tzinfo=None) < since:
                    break
                
                # Пропускаем сообщения без текста
                if not msg.text:
                    continue
                
                # Формируем ссылку
                if username:
                    link = f"https://t.me/{username}/{msg.id}"
                else:
                    link = f"https://t.me/c/{channel_id}/{msg.id}"
                
                messages.append(MessageInfo(
                    channel_id=channel_id,
                    channel_title=title,
                    message_id=msg.id,
                    text=msg.text[:1000],  # Ограничиваем текст
                    date=msg.date.replace(tzinfo=None),
                    views=msg.views,
                    link=link,
                ))
            
            if messages:
                all_messages.extend(messages)
                channels_with_messages += 1
                
        except ChannelPrivateError:
            logger.warning(f"Канал {title} приватный — пропускаем")
        except ChannelInvalidError:
            logger.warning(f"Канал {title} недоступен — пропускаем")
        except Exception as e:
            logger.error(f"Ошибка загрузки {title}: {e}")
    
    logger.info(f"Всего загружено {len(all_messages)} сообщений из {channels_with_messages} каналов")
    
    return all_messages


async def get_channel_messages(
    channel_id: int,
    title: str,
    username: str | None,
    since: datetime,
    until: datetime,
    limit: int = 50,
) -> list[MessageInfo]:
    """
    Получает сообщения из одного канала.
    
    Обёртка для get_messages_from_channels для одного канала.
    """
    return await get_messages_from_channels(
        channels=[(channel_id, title, username)],
        since=since,
        until=until,
        limit_per_channel=limit,
    )


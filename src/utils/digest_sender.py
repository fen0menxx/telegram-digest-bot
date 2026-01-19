"""
Общие утилиты для отправки дайджестов.

Используется как в ручных запросах (handlers/digest.py),
так и в автоматических дайджестах (scheduler/tasks.py).
"""

import asyncio
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from loguru import logger
from sqlalchemy import select

from src.storage.database import get_session
from src.storage.models import ProcessedMessage
from src.userbot.messages import MessageInfo


# Папка для резервных копий дайджестов
DIGEST_BACKUP_DIR = Path(__file__).parent.parent.parent / "data" / "digest_backups"
DIGEST_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


async def filter_cached_messages(
    messages: list[MessageInfo],
) -> tuple[list[MessageInfo], int]:
    """
    Фильтрует уже обработанные сообщения.
    
    Returns:
        (новые сообщения, количество пропущенных из кэша)
    """
    if not messages:
        return [], 0
    
    # Получаем все ID сообщений для проверки
    message_keys = [(msg.channel_id, msg.message_id) for msg in messages]
    
    async with get_session() as session:
        # Получаем уже обработанные
        result = await session.execute(
            select(ProcessedMessage.channel_id, ProcessedMessage.message_id)
        )
        processed = {(row[0], row[1]) for row in result.fetchall()}
    
    # Фильтруем
    new_messages = [
        msg for msg in messages
        if (msg.channel_id, msg.message_id) not in processed
    ]
    
    cached_count = len(messages) - len(new_messages)
    
    if cached_count > 0:
        logger.info(f"Пропущено из кэша: {cached_count} сообщений")
    
    return new_messages, cached_count


async def cache_processed_messages(messages: list[MessageInfo]) -> None:
    """Сохраняет обработанные сообщения в кэш."""
    if not messages:
        return
    
    async with get_session() as session:
        for msg in messages:
            # Проверяем, нет ли уже в кэше
            result = await session.execute(
                select(ProcessedMessage).where(
                    ProcessedMessage.channel_id == msg.channel_id,
                    ProcessedMessage.message_id == msg.message_id,
                )
            )
            if result.scalar_one_or_none() is None:
                cached = ProcessedMessage(
                    channel_id=msg.channel_id,
                    message_id=msg.message_id,
                )
                session.add(cached)
        
        await session.commit()
    
    logger.info(f"Закэшировано: {len(messages)} сообщений")


def save_digest_backup(
    cluster_name: str,
    digest_text: str,
    message_count: int,
    period: str,
) -> Path:
    """
    Сохраняет резервную копию дайджеста в файл.
    
    Используется для восстановления если Telegram API упал после генерации.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = cluster_name.replace(" ", "_").replace("/", "_")[:30]
    filename = f"{timestamp}_{safe_name}.txt"
    filepath = DIGEST_BACKUP_DIR / filename
    
    content = f"""=== РЕЗЕРВНАЯ КОПИЯ ДАЙДЖЕСТА ===
Время: {datetime.now().isoformat()}
Кластер: {cluster_name}
Период: {period}
Сообщений: {message_count}
=====================================

{digest_text}
"""
    
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"💾 Дайджест сохранён в: {filepath}")
    return filepath


def smart_split_html(text: str, max_len: int = 4000) -> list[str]:
    """
    Умно разбивает HTML-текст на части, не разрезая теги.
    
    Разбиваем по переносам строк, чтобы не разрезать теги пополам.
    """
    if len(text) <= max_len:
        return [text]
    
    parts = []
    lines = text.split('\n')
    current_part = ""
    
    for line in lines:
        # Если добавление этой строки не превысит лимит
        if len(current_part) + len(line) + 1 <= max_len:
            current_part += line + '\n'
        else:
            # Сохраняем текущую часть
            if current_part.strip():
                parts.append(current_part.strip())
            
            # Если одна строка больше лимита — режем её (крайний случай)
            if len(line) > max_len:
                # Режем по словам
                words = line.split(' ')
                current_part = ""
                for word in words:
                    if len(current_part) + len(word) + 1 <= max_len:
                        current_part += word + ' '
                    else:
                        if current_part.strip():
                            parts.append(current_part.strip())
                        current_part = word + ' '
            else:
                current_part = line + '\n'
    
    # Добавляем последнюю часть
    if current_part.strip():
        parts.append(current_part.strip())
    
    return parts if parts else [text[:max_len]]


async def send_digest_to_channel(
    bot: Bot,
    channel_id: int,
    text: str,
    thread_id: int | None = None,
    max_retries: int = 3,
) -> bool:
    """
    Отправляет дайджест в канал/группу.
    
    Args:
        bot: Экземпляр бота
        channel_id: ID канала/группы
        text: Текст дайджеста
        thread_id: ID топика (для групп с топиками)
        max_retries: Количество попыток
    
    Returns:
        True если отправка успешна, False если все попытки провалились.
    """
    for attempt in range(1, max_retries + 1):
        try:
            # Telegram ограничивает сообщение 4096 символами
            if len(text) > 4000:
                # Умно разбиваем на части, не разрезая теги
                parts = smart_split_html(text, max_len=4000)
                
                for part in parts:
                    await bot.send_message(
                        channel_id, 
                        part, 
                        parse_mode="HTML",
                        message_thread_id=thread_id,
                    )
            else:
                await bot.send_message(
                    channel_id, 
                    text, 
                    parse_mode="HTML",
                    message_thread_id=thread_id,
                )
            
            return True  # Успех!
            
        except TelegramRetryAfter as e:
            # Telegram просит подождать
            wait_time = e.retry_after
            logger.warning(f"Telegram rate limit. Ждём {wait_time} сек...")
            await asyncio.sleep(wait_time)
            continue
            
        except TelegramAPIError as e:
            logger.error(f"Попытка {attempt}/{max_retries} не удалась: {e}")
            
            if attempt < max_retries:
                wait_time = attempt * 2  # Exponential backoff: 2, 4 сек
                logger.info(f"Повтор через {wait_time} сек...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Все {max_retries} попытки отправки провалились")
                return False
    
    return False


async def send_to_user_or_channel(
    bot: Bot,
    user_id: int,
    text: str,
    channel_id: int | None = None,
    thread_id: int | None = None,
    max_retries: int = 3,
) -> bool:
    """
    Отправляет дайджест в канал (если указан) или пользователю напрямую.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя (fallback)
        text: Текст дайджеста
        channel_id: ID канала (если None — отправляем user_id)
        thread_id: ID топика
        max_retries: Количество попыток
    
    Returns:
        True если отправка успешна
    """
    target_id = channel_id if channel_id else user_id
    
    return await send_digest_to_channel(
        bot=bot,
        channel_id=target_id,
        text=text,
        thread_id=thread_id if channel_id else None,
        max_retries=max_retries,
    )


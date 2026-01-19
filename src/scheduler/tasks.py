"""
Планировщик задач для автоматических дайджестов.

Использует APScheduler для периодических задач.

Особенности:
- Автоматический дайджест отправляется в указанный канал (digest_channel_id)
- Генерируется ОТДЕЛЬНЫЙ дайджест для КАЖДОГО кластера
- Catch-up собирает сообщения за сегодня и вчера (с 00:00 вчера)
- Кэширование только после успешной отправки
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy import select

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.storage.database import get_session
from src.storage.models import User, Cluster, Channel, DigestHistory
from src.userbot.messages import get_messages_from_channels
from src.ai.summarizer import summarize_messages
from src.utils.digest_sender import (
    filter_cached_messages,
    cache_processed_messages,
    save_digest_backup,
    send_to_user_or_channel,
)

# Глобальный планировщик
scheduler = AsyncIOScheduler()

# Ссылка на бота для отправки сообщений
_bot = None


def set_bot(bot) -> None:
    """Установить экземпляр бота для отправки сообщений."""
    global _bot
    _bot = bot


async def check_and_send_digests() -> None:
    """
    Проверить и отправить дайджесты пользователям.
    
    Запускается по расписанию. Проверяет, пора ли отправлять дайджест
    каждому пользователю на основе его настроек.
    """
    logger.info("Проверка дайджестов по расписанию...")
    
    if _bot is None:
        logger.error("Бот не инициализирован для планировщика")
        return
    
    async with get_session() as session:
        # Получаем активных пользователей
        result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = result.scalars().all()
    
    now = datetime.utcnow()
    
    for user in users:
        try:
            await _process_user_digest(user, now)
        except Exception as e:
            logger.error(f"Ошибка дайджеста для {user.telegram_id}: {e}")


async def _process_user_digest(user: User, now: datetime) -> None:
    """
    Обработать дайджесты для одного пользователя.
    
    Логика:
    - Генерируем ОТДЕЛЬНЫЙ дайджест для КАЖДОГО кластера
    - Период: вчера 00:00 — сейчас (максимум 2 дня)
    - Без ограничений по количеству сообщений
    - Отправка в указанный канал (если настроен)
    - Кэширование только после успешной отправки
    """
    # Вычисляем, когда должен быть следующий дайджест
    if user.last_digest_at is None:
        # Первый дайджест — отправляем сразу
        should_send = True
    else:
        next_digest = user.last_digest_at + timedelta(hours=user.digest_interval)
        should_send = now >= next_digest
    
    if not should_send:
        return
    
    # === НОВАЯ ЛОГИКА: период = вчера 00:00 — сейчас ===
    # Максимум собираем за 2 дня, даже если бот не запускался неделю
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = today_start - timedelta(days=1)  # Вчера 00:00
    period_label = f"вчера и сегодня ({since.strftime('%d.%m')} — {now.strftime('%d.%m')})"
    
    # Получаем все кластеры пользователя
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.user_id == user.telegram_id)
        )
        clusters = result.scalars().all()
        
        if not clusters:
            logger.debug(f"У пользователя {user.telegram_id} нет кластеров")
            return
    
    # Получаем настройки пользователя для отправки
    news_limit = getattr(user, 'digest_news_limit', 20) or 20
    digest_channel_id = getattr(user, 'digest_channel_id', None)
    digest_thread_id = getattr(user, 'digest_thread_id', None)
    
    logger.info(
        f"Отправка дайджестов пользователю {user.telegram_id}, "
        f"кластеров: {len(clusters)}, период: {period_label}"
    )
    
    # === ОБРАБАТЫВАЕМ КАЖДЫЙ КЛАСТЕР ОТДЕЛЬНО ===
    total_sent = 0
    
    for cluster in clusters:
        try:
            sent = await _process_cluster_digest(
                user=user,
                cluster=cluster,
                since=since,
                now=now,
                period_label=period_label,
                news_limit=news_limit,
                digest_channel_id=digest_channel_id,
                digest_thread_id=digest_thread_id,
            )
            if sent:
                total_sent += 1
        except Exception as e:
            logger.error(f"Ошибка дайджеста кластера {cluster.name}: {e}")
    
    # Обновляем время последнего дайджеста (если хотя бы один отправлен)
    if total_sent > 0:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.telegram_id)
            )
            db_user = result.scalar_one()
            db_user.last_digest_at = now
            await session.commit()
        
        logger.success(f"Отправлено {total_sent} дайджестов пользователю {user.telegram_id}")


async def _process_cluster_digest(
    user: User,
    cluster: Cluster,
    since: datetime,
    now: datetime,
    period_label: str,
    news_limit: int,
    digest_channel_id: int | None,
    digest_thread_id: int | None,
) -> bool:
    """
    Обработать дайджест для одного кластера.
    
    Returns:
        True если дайджест успешно отправлен
    """
    cluster_name = cluster.name
    
    # Получаем каналы кластера
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster.id)
        )
        channels = result.scalars().all()
    
    if not channels:
        logger.debug(f"Кластер {cluster_name} пуст — пропускаем")
        return False
    
    # Собираем сообщения
    channels_data = [
        (ch.telegram_id, ch.title, ch.username)
        for ch in channels
    ]
    
    all_messages = await get_messages_from_channels(
        channels=channels_data,
        since=since,
        until=now,
        limit_per_channel=100,
    )
    
    # Фильтруем уже обработанные (кэш)
    messages, cached_count = await filter_cached_messages(all_messages)
    
    if not messages:
        if cached_count > 0:
            logger.debug(f"Кластер {cluster_name}: все {cached_count} сообщений в кэше")
        else:
            logger.debug(f"Кластер {cluster_name}: нет новых сообщений")
        return False
    
    logger.info(f"Кластер {cluster_name}: {len(messages)} новых сообщений")
    
    # Генерируем дайджест
    digest_text = await summarize_messages(messages, cluster_name, news_limit=news_limit)
    
    # Сохраняем резервную копию СРАЗУ после генерации AI
    backup_path = save_digest_backup(
        cluster_name=f"{cluster_name} (авто)",
        digest_text=digest_text,
        message_count=len(messages),
        period=period_label,
    )
    
    # Отправляем в канал (если указан) или пользователю
    send_success = await send_to_user_or_channel(
        bot=_bot,
        user_id=user.telegram_id,
        text=digest_text,
        channel_id=digest_channel_id,
        thread_id=digest_thread_id,
        max_retries=3,
    )
    
    if not send_success:
        logger.error(
            f"Не удалось отправить дайджест {cluster_name} после 3 попыток. "
            f"Резервная копия: {backup_path}"
        )
        return False
    
    # === УСПЕШНАЯ ОТПРАВКА ===
    # Только теперь кэшируем сообщения!
    await cache_processed_messages(messages)
    
    # Сохраняем в историю
    async with get_session() as session:
        history = DigestHistory(
            user_id=user.telegram_id,
            cluster_id=cluster.id,
            period_start=since,
            period_end=now,
            content=digest_text,
            message_count=len(messages),
        )
        session.add(history)
        await session.commit()
    
    destination = "в канал" if digest_channel_id else "пользователю"
    logger.success(f"Дайджест {cluster_name} отправлен {destination}")
    
    return True


async def catch_up_digests() -> None:
    """
    Catch-up: отправить пропущенные дайджесты при запуске.
    
    Вызывается при старте бота. Проверяет, были ли пропущены
    дайджесты, пока бот был выключен.
    """
    logger.info("Проверка пропущенных дайджестов (catch-up)...")
    
    await check_and_send_digests()


def start_scheduler() -> None:
    """Запустить планировщик."""
    # Проверяем каждый час
    scheduler.add_job(
        check_and_send_digests,
        IntervalTrigger(hours=1),
        id="digest_check",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Планировщик запущен (проверка каждый час)")


def stop_scheduler() -> None:
    """Остановить планировщик."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Планировщик остановлен")


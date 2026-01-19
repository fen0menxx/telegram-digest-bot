"""
Обработчики получения дайджестов.

Ручной запрос дайджеста по кластеру или всем каналам.
Использует Reply-клавиатуры.

Защита токенов:
- Кэширование сообщений ТОЛЬКО после успешной отправки
- Retry (3 попытки) при ошибке Telegram API
- Логирование дайджестов в файл для резервного восстановления
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from loguru import logger
from sqlalchemy import select

# Папка для резервных копий дайджестов
DIGEST_BACKUP_DIR = Path(__file__).parent.parent.parent.parent / "data" / "digest_backups"
DIGEST_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.bot.keyboards import (
    get_main_menu_keyboard,
    get_digest_menu_keyboard,
    get_digest_period_reply_keyboard,
    get_digest_clusters_keyboard,
)
from src.bot.states import MenuStates
from src.storage.database import get_session
from src.storage.models import Cluster, Channel, User, DigestHistory, ProcessedMessage
from src.userbot.messages import get_messages_from_channels, MessageInfo
from src.ai.summarizer import summarize_messages
from src.utils.digest_sender import (
    filter_cached_messages,
    cache_processed_messages,
    save_digest_backup,
    send_digest_to_channel,
    smart_split_html,
)

router = Router(name="digest")


async def send_with_retry(
    message: Message,
    text: str,
    max_retries: int = 3,
) -> bool:
    """
    Отправляет сообщение в чат с retry.
    
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
                    await message.answer(part, parse_mode="HTML")
            else:
                await message.answer(text, parse_mode="HTML")
            
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


# =============================================================================
# МЕНЮ ДАЙДЖЕСТА
# =============================================================================

@router.message(Command("digest"))
async def cmd_digest(message: Message, state: FSMContext) -> None:
    """Команда /digest."""
    await show_digest_menu(message, state)


@router.message(F.text == "📊 Дайджест")
async def msg_digest(message: Message, state: FSMContext) -> None:
    """Переход в меню дайджеста."""
    await show_digest_menu(message, state)


async def show_digest_menu(message: Message, state: FSMContext) -> None:
    """Показать меню выбора кластера для дайджеста."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.user_id == user_id)
        )
        clusters = result.scalars().all()
    
    if not clusters:
        await message.answer(
            "📊 <b>Дайджест</b>\n\n"
            "У вас пока нет кластеров.\n"
            "Создайте кластер и добавьте в него каналы,\n"
            "чтобы получать дайджесты.",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    
    clusters_data = [(c.id, c.name) for c in clusters]
    
    await state.set_state(MenuStates.digest_select_cluster)
    
    await message.answer(
        "📊 <b>Выберите кластер для дайджеста:</b>\n\n"
        "Или нажмите «📊 Все кластеры» для общего дайджеста",
        reply_markup=get_digest_menu_keyboard(),
    )
    await message.answer(
        "👇 <b>Кластеры:</b>",
        reply_markup=get_digest_clusters_keyboard(clusters_data),
    )


@router.message(F.text == "📊 Все кластеры", MenuStates.digest_select_cluster)
async def msg_digest_all(message: Message, state: FSMContext) -> None:
    """Дайджест по всем кластерам."""
    await state.update_data(digest_cluster_id="all")
    await state.set_state(MenuStates.digest_select_period)
    
    await message.answer(
        "📅 <b>За какой период собрать дайджест?</b>",
        reply_markup=get_digest_period_reply_keyboard(),
    )


@router.callback_query(F.data.startswith("digest_cluster:"))
async def cb_digest_cluster(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбран кластер — показываем выбор периода."""
    cluster_param = callback.data.split(":")[1]
    
    await state.update_data(digest_cluster_id=cluster_param)
    await state.set_state(MenuStates.digest_select_period)
    
    await callback.message.answer(
        "📅 <b>За какой период собрать дайджест?</b>",
        reply_markup=get_digest_period_reply_keyboard(),
    )
    await callback.answer()


# =============================================================================
# ВЫБОР ПЕРИОДА
# =============================================================================

@router.message(F.text.startswith("📅"), MenuStates.digest_select_period)
async def msg_digest_period(message: Message, state: FSMContext) -> None:
    """Обработка выбора периода."""
    text = message.text
    
    # Определяем период
    if "сегодня" in text.lower():
        period_hours = 1
    elif "вчера" in text.lower():
        period_hours = 24
    elif "2 дня" in text.lower():
        period_hours = 48
    elif "3 дня" in text.lower():
        period_hours = 72
    elif "7 дней" in text.lower():
        period_hours = 168
    else:
        await message.answer("Пожалуйста, выберите период из кнопок ниже.")
        return
    
    await process_digest(message, state, period_hours)


@router.message(F.text == "🔄 С последнего дайджеста", MenuStates.digest_select_period)
async def msg_digest_from_last(message: Message, state: FSMContext) -> None:
    """Дайджест с последнего дайджеста."""
    await process_digest(message, state, 0)


async def process_digest(message: Message, state: FSMContext, period_hours: int) -> None:
    """Генерация дайджеста."""
    data = await state.get_data()
    cluster_param = data.get("digest_cluster_id", "all")
    user_id = message.from_user.id
    
    now = datetime.utcnow()
    
    # Определяем период
    if period_hours == 0:
        # С последнего дайджеста
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user and user.last_digest_at:
                since = user.last_digest_at
                period_label = f"с {since.strftime('%d.%m.%Y %H:%M')}"
            else:
                since = now - timedelta(hours=24)
                period_label = "за последние 24 часа"
    else:
        # Считаем от начала дня (00:00), а не от текущего момента
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if period_hours == 1:
            # "За сегодня" = с 00:00 сегодня
            since = today_start
            period_label = f"за сегодня (с 00:00)"
        elif period_hours == 24:
            # "За вчера" = с 00:00 вчера до 00:00 сегодня
            since = today_start - timedelta(days=1)
            period_label = f"за вчера ({since.strftime('%d.%m')})"
        elif period_hours == 48:
            # "За 2 дня" = с 00:00 позавчера
            since = today_start - timedelta(days=2)
            period_label = f"за 2 дня (с {since.strftime('%d.%m')})"
        elif period_hours == 72:
            # "За 3 дня" = с 00:00 3 дня назад
            since = today_start - timedelta(days=3)
            period_label = f"за 3 дня (с {since.strftime('%d.%m')})"
        elif period_hours == 168:
            # "За 7 дней" = с 00:00 неделю назад
            since = today_start - timedelta(days=7)
            period_label = f"за 7 дней (с {since.strftime('%d.%m')})"
        else:
            since = now - timedelta(hours=period_hours)
            period_label = f"за {period_hours} часов"
    
    # Получаем каналы и настройки пользователя
    async with get_session() as session:
        # Получаем лимит важных новостей из настроек пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user_obj = result.scalar_one_or_none()
        news_limit = getattr(user_obj, 'digest_news_limit', 20) if user_obj else 20
        
        if cluster_param == "all":
            result = await session.execute(
                select(Cluster).where(Cluster.user_id == user_id)
            )
            clusters = result.scalars().all()
            cluster_ids = [c.id for c in clusters]
            cluster_name = "Все кластеры"
            
            result = await session.execute(
                select(Channel).where(Channel.cluster_id.in_(cluster_ids))
            )
        else:
            cluster_id = int(cluster_param)
            result = await session.execute(
                select(Cluster).where(Cluster.id == cluster_id)
            )
            cluster = result.scalar_one_or_none()
            
            if not cluster:
                await message.answer(
                    "❌ Кластер не найден",
                    reply_markup=get_main_menu_keyboard(),
                )
                return
            
            cluster_name = cluster.name
            
            result = await session.execute(
                select(Channel).where(Channel.cluster_id == cluster_id)
            )
        
        channels = result.scalars().all()
    
    if not channels:
        await message.answer(
            f"📊 <b>Дайджест: {cluster_name}</b>\n\n"
            "В этом кластере нет каналов.\n"
            "Добавьте каналы через редактирование кластера.",
            reply_markup=get_main_menu_keyboard(),
        )
        await state.set_state(MenuStates.main_menu)
        return
    
    # Уведомляем о начале сбора
    status_msg = await message.answer(
        f"⏳ <b>Собираю дайджест...</b>\n\n"
        f"📁 Кластер: {cluster_name}\n"
        f"📢 Каналов: {len(channels)}\n"
        f"📅 Период: {period_label}"
    )
    
    try:
        # Собираем сообщения
        channels_data = [
            (ch.telegram_id, ch.title, ch.username)
            for ch in channels
        ]
        
        all_messages = await get_messages_from_channels(
            channels=channels_data,
            since=since,
            until=now,
            limit_per_channel=50,  # Загружаем достаточно сообщений
        )
        
        # Фильтруем уже обработанные (кэш)
        messages, cached_count = await filter_cached_messages(all_messages)
        
        if not messages:
            cached_info = f"\n💾 Из кэша: {cached_count} уже обработано ранее" if cached_count > 0 else ""
            await status_msg.edit_text(
                f"📊 <b>Дайджест: {cluster_name}</b>\n\n"
                f"📅 Период: {period_label}\n\n"
                f"Новых сообщений не найдено.{cached_info}"
            )
            await state.set_state(MenuStates.main_menu)
            return
        
        # Генерируем дайджест через AI
        cached_info = f" (💾 {cached_count} из кэша)" if cached_count > 0 else ""
        await status_msg.edit_text(
            f"🤖 <b>Генерирую дайджест...</b>\n\n"
            f"📝 Обрабатываю {len(messages)} новых сообщений{cached_info}..."
        )
        
        digest_text = await summarize_messages(messages, cluster_name, news_limit=news_limit)
        
        # === ЗАЩИТА ТОКЕНОВ ===
        # Сохраняем резервную копию СРАЗУ после генерации AI
        # Если Telegram упадёт, дайджест не потеряется
        backup_path = save_digest_backup(
            cluster_name=cluster_name,
            digest_text=digest_text,
            message_count=len(messages),
            period=period_label,
        )
        
        # Получаем канал и топик для отправки из настроек
        digest_channel_id = getattr(user_obj, 'digest_channel_id', None) if user_obj else None
        digest_thread_id = getattr(user_obj, 'digest_thread_id', None) if user_obj else None
        
        # Отправляем с retry (3 попытки)
        if digest_channel_id:
            # Отправляем в канал (с топиком если указан)
            bot = message.bot
            send_success = await send_digest_to_channel(
                bot, digest_channel_id, digest_text, 
                thread_id=digest_thread_id, max_retries=3
            )
            destination = "в канал" + (f" (топик {digest_thread_id})" if digest_thread_id else "")
        else:
            # Отправляем в бота
            send_success = await send_with_retry(message, digest_text, max_retries=3)
            destination = "в бота"
        
        if not send_success:
            # Отправка не удалась после всех попыток
            # Сообщения НЕ кэшируем — при следующем запросе попробуем снова
            # Но дайджест сохранён в файле!
            error_msg = (
                f"❌ <b>Не удалось отправить дайджест {destination}</b>\n\n"
                f"Telegram API недоступен после 3 попыток.\n\n"
            )
            if digest_channel_id:
                error_msg += (
                    f"Проверьте:\n"
                    f"• Бот добавлен в канал как администратор?\n"
                    f"• ID канала правильный? (<code>{digest_channel_id}</code>)\n\n"
                )
            error_msg += (
                f"💾 Дайджест сохранён в файл:\n"
                f"<code>{backup_path.name}</code>\n\n"
                f"Токены НЕ потрачены впустую — при следующем запросе "
                f"те же сообщения будут обработаны снова."
            )
            await status_msg.edit_text(error_msg)
            await state.set_state(MenuStates.main_menu)
            return
        
        # Уведомляем пользователя об успешной отправке в канал
        if digest_channel_id:
            await status_msg.edit_text(
                f"✅ <b>Дайджест отправлен в канал!</b>\n\n"
                f"📁 Кластер: {cluster_name}\n"
                f"📝 Сообщений: {len(messages)}\n"
                f"📅 Период: {period_label}"
            )
        else:
            # Убираем статус, дайджест уже отправлен
            await status_msg.delete()
        
        # === УСПЕШНАЯ ОТПРАВКА ===
        # Только теперь кэшируем сообщения!
        await cache_processed_messages(messages)
        
        # Сохраняем в историю
        async with get_session() as session:
            # Обновляем last_digest_at
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one()
            user.last_digest_at = now
            
            # Сохраняем дайджест
            history = DigestHistory(
                user_id=user_id,
                cluster_id=int(cluster_param) if cluster_param != "all" else None,
                period_start=since,
                period_end=now,
                content=digest_text,
                message_count=len(messages),
            )
            session.add(history)
            await session.commit()
        
        logger.info(
            f"✅ Дайджест отправлен: {cluster_name}, "
            f"{len(messages)} сообщений, период: {period_label}"
        )
        
        await state.set_state(MenuStates.main_menu)
        
    except Exception as e:
        logger.error(f"Ошибка генерации дайджеста: {e}")
        await status_msg.edit_text(
            f"❌ <b>Ошибка генерации дайджеста</b>\n\n"
            f"Попробуйте позже или проверьте логи.\n"
            f"Ошибка: {str(e)[:200]}\n\n"
            f"💡 Сообщения НЕ закэшированы — повторный запрос обработает их снова."
        )
        await state.set_state(MenuStates.main_menu)


# =============================================================================
# LEGACY CALLBACKS
# =============================================================================

@router.callback_query(F.data == "digest")
async def cb_digest(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка дайджеста в меню (legacy)."""
    await callback.message.answer(
        "Используйте кнопки внизу экрана 👇",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "digest_back")
async def cb_digest_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Назад к выбору кластера (legacy)."""
    await callback.message.answer(
        "Используйте кнопку «🔙 Назад» внизу экрана",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("digest_period:"))
async def cb_digest_period(callback: CallbackQuery, state: FSMContext) -> None:
    """Legacy callback для периода."""
    await callback.message.answer(
        "Выберите период кнопками внизу экрана 👇",
        reply_markup=get_digest_period_reply_keyboard(),
    )
    await callback.answer()

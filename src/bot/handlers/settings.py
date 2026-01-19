"""
Обработчики настроек пользователя.

Интервал дайджестов, лимит новостей, канал для отправки.
Использует Reply-клавиатуры.
"""

import re
import sys
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.bot.keyboards import (
    get_main_menu_keyboard,
    get_settings_menu_keyboard,
    get_interval_keyboard,
    get_digest_news_limit_keyboard,
    get_cancel_keyboard,
)
from src.bot.states import MenuStates, InputStates
from src.storage.database import get_session
from src.storage.models import User

router = Router(name="settings")


# =============================================================================
# МЕНЮ НАСТРОЕК
# =============================================================================

@router.message(F.text == "⚙️ Настройки")
async def msg_settings(message: Message, state: FSMContext) -> None:
    """Переход в меню настроек."""
    await show_settings(message, state)


async def show_settings(message: Message, state: FSMContext) -> None:
    """Показать настройки."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("Пользователь не найден")
        return
    
    # Форматируем интервал
    interval = user.digest_interval
    if interval < 24:
        interval_text = f"каждые {interval} ч."
    elif interval == 24:
        interval_text = "раз в день"
    elif interval == 48:
        interval_text = "раз в 2 дня"
    elif interval == 168:
        interval_text = "раз в неделю"
    else:
        interval_text = f"каждые {interval} ч."
    
    # Лимит новостей
    news_limit = getattr(user, 'digest_news_limit', 20) or 20
    
    # Канал для дайджестов
    channel_id = getattr(user, 'digest_channel_id', None)
    thread_id = getattr(user, 'digest_thread_id', None)
    
    if channel_id:
        channel_text = f"ID: <code>{channel_id}</code>"
        if thread_id:
            channel_text += f" (топик: {thread_id})"
    else:
        channel_text = "не указан (в бота)"
    
    await state.set_state(MenuStates.settings_menu)
    
    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"⏰ Интервал: <b>{interval_text}</b>\n"
        f"📰 Лимит важных новостей: <b>до {news_limit}</b>\n"
        f"📢 Канал для дайджестов: {channel_text}",
        reply_markup=get_settings_menu_keyboard(),
    )


# =============================================================================
# ИНТЕРВАЛ ДАЙДЖЕСТОВ
# =============================================================================

@router.message(F.text == "⏰ Интервал дайджестов", MenuStates.settings_menu)
async def msg_settings_interval(message: Message, state: FSMContext) -> None:
    """Выбор интервала."""
    await message.answer(
        "⏰ <b>Интервал автоматических дайджестов</b>\n\n"
        "Как часто отправлять дайджесты?\n\n"
        "Выберите из списка:",
        reply_markup=get_settings_menu_keyboard(),
    )
    await message.answer(
        "👇 <b>Интервал:</b>",
        reply_markup=get_interval_keyboard(),
    )


@router.callback_query(F.data.startswith("set_interval:"))
async def cb_set_interval(callback: CallbackQuery, state: FSMContext) -> None:
    """Установка интервала."""
    hours = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.digest_interval = hours
            await session.commit()
    
    await callback.answer(f"✅ Интервал установлен: {hours} ч.", show_alert=True)
    
    # Показываем обновлённые настройки
    await show_settings(callback.message, state)


# =============================================================================
# ЛИМИТ НОВОСТЕЙ
# =============================================================================

@router.message(F.text == "📰 Лимит важных новостей", MenuStates.settings_menu)
async def msg_settings_news_limit(message: Message, state: FSMContext) -> None:
    """Выбор лимита новостей."""
    await message.answer(
        "📰 <b>Лимит важных новостей</b>\n\n"
        "Сколько важных новостей включать в дайджест?\n\n"
        "Выберите из списка:",
        reply_markup=get_settings_menu_keyboard(),
    )
    await message.answer(
        "👇 <b>Лимит:</b>",
        reply_markup=get_digest_news_limit_keyboard(),
    )


@router.callback_query(F.data.startswith("set_news_limit:"))
async def cb_set_news_limit(callback: CallbackQuery, state: FSMContext) -> None:
    """Установка лимита новостей."""
    limit = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.digest_news_limit = limit
            await session.commit()
    
    await callback.answer(f"✅ Лимит установлен: до {limit} новостей", show_alert=True)
    
    # Показываем обновлённые настройки
    await show_settings(callback.message, state)


# =============================================================================
# КАНАЛ ДЛЯ ДАЙДЖЕСТОВ
# =============================================================================

@router.message(F.text == "📢 Канал для дайджестов", MenuStates.settings_menu)
async def msg_settings_digest_channel(message: Message, state: FSMContext) -> None:
    """Настройка канала для дайджестов."""
    await state.set_state(InputStates.waiting_channel_link)
    
    await message.answer(
        "📢 <b>Канал для дайджестов</b>\n\n"
        "Отправьте ссылку на канал/группу или топик, куда отправлять дайджесты.\n\n"
        "Примеры:\n"
        "• <code>https://t.me/c/1234567890/123</code> — топик в группе\n"
        "• <code>https://t.me/mychannel</code> — публичный канал\n"
        "• <code>-1001234567890</code> — ID канала\n\n"
        "Или отправьте <code>0</code> чтобы отправлять в бота.",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(InputStates.waiting_channel_link)
async def process_channel_link(message: Message, state: FSMContext) -> None:
    """Обработка ссылки на канал."""
    text = message.text.strip()
    user_id = message.from_user.id
    
    if text == "❌ Отмена":
        await state.set_state(MenuStates.settings_menu)
        await show_settings(message, state)
        return
    
    channel_id = None
    thread_id = None
    
    # Сброс — отправлять в бота
    if text == "0":
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.digest_channel_id = None
                user.digest_thread_id = None
                await session.commit()
        
        await state.set_state(MenuStates.settings_menu)
        await message.answer(
            "✅ Дайджесты будут отправляться в бота.",
            reply_markup=get_settings_menu_keyboard(),
        )
        return
    
    # Парсим ссылку t.me/c/CHANNEL_ID/THREAD_ID
    match = re.search(r't\.me/c/(\d+)/(\d+)', text)
    if match:
        channel_id = -int("100" + match.group(1))  # Конвертируем в Telegram ID
        thread_id = int(match.group(2))
    else:
        # Парсим просто ID
        match = re.match(r'^-?\d+$', text)
        if match:
            channel_id = int(text)
    
    if channel_id is None:
        await message.answer(
            "❌ Не удалось распознать ссылку.\n\n"
            "Отправьте ссылку в формате:\n"
            "• <code>https://t.me/c/1234567890/123</code>\n"
            "• <code>-1001234567890</code>",
        )
        return
    
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.digest_channel_id = channel_id
            user.digest_thread_id = thread_id
            await session.commit()
    
    await state.set_state(MenuStates.settings_menu)
    
    thread_text = f" (топик: {thread_id})" if thread_id else ""
    await message.answer(
        f"✅ Канал для дайджестов установлен!\n\n"
        f"ID: <code>{channel_id}</code>{thread_text}\n\n"
        "⚠️ Убедитесь, что бот добавлен в канал как администратор!",
        reply_markup=get_settings_menu_keyboard(),
    )


# =============================================================================
# LEGACY CALLBACKS
# =============================================================================

@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню настроек (legacy)."""
    await callback.message.answer(
        "Используйте кнопки внизу экрана 👇",
        reply_markup=get_settings_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_interval")
async def cb_settings_interval(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор интервала (legacy)."""
    await msg_settings_interval(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "settings_news_limit")
async def cb_settings_news_limit(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор лимита (legacy)."""
    await msg_settings_news_limit(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "settings_digest_channel")
async def cb_settings_digest_channel(callback: CallbackQuery, state: FSMContext) -> None:
    """Настройка канала (legacy)."""
    await msg_settings_digest_channel(callback.message, state)
    await callback.answer()

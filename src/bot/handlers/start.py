"""
Обработчики команд /start и /menu.

Точка входа в бота, главное меню.
"""

import sys
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.bot.keyboards import get_main_menu_keyboard
from src.bot.states import MenuStates
from src.storage.database import get_session
from src.storage.models import User

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Команда /start."""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Создаём пользователя если не существует
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            user = User(telegram_id=user_id, username=username)
            session.add(user)
            await session.commit()
    
    await state.set_state(MenuStates.main_menu)
    
    await message.answer(
        "👋 <b>Добро пожаловать в Telegram Digest Bot!</b>\n\n"
        "Я помогу вам создавать дайджесты из ваших Telegram-каналов.\n\n"
        "📁 <b>Кластеры</b> — группируйте каналы по тематикам\n"
        "📊 <b>Дайджест</b> — получайте сводку новостей\n"
        "🔄 <b>Сканировать</b> — обновить список каналов\n"
        "⚙️ <b>Настройки</b> — настроить автодайджесты",
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    """Команда /menu."""
    await state.set_state(MenuStates.main_menu)
    await message.answer(
        "📱 <b>Главное меню</b>",
        reply_markup=get_main_menu_keyboard(),
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню (callback, legacy)."""
    await state.set_state(MenuStates.main_menu)
    await callback.message.answer(
        "📱 <b>Главное меню</b>",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Пустой callback (для кнопок-заглушек)."""
    await callback.answer()

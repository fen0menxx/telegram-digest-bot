"""
Middleware для бота.

OwnerMiddleware — пропускает только владельца бота.
"""

import sys
from pathlib import Path
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings


class OwnerMiddleware(BaseMiddleware):
    """Middleware: пропускает только владельца бота."""
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        
        if user_id != settings.OWNER_ID:
            # Игнорируем сообщения не от владельца
            if isinstance(event, Message):
                await event.answer("⛔ Бот доступен только владельцу.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Нет доступа", show_alert=True)
            return
        
        return await handler(event, data)


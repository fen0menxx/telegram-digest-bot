"""
Инициализация и управление базой данных.

Использует SQLAlchemy async с aiosqlite.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.storage.models import Base

# Создаём async engine
engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.DB_PATH}",
    echo=False,
)

# Фабрика сессий
async_session = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Контекстный менеджер для получения сессии."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Инициализация базы данных — создание таблиц."""
    logger.info("Инициализация базы данных...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.success("База данных инициализирована")






























"""
Модели SQLAlchemy для базы данных.

Таблицы:
- users: пользователи бота
- clusters: тематические кластеры каналов
- channels: Telegram каналы/группы
- digest_history: история дайджестов
- processed_messages: кэш обработанных сообщений
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для моделей."""
    pass


class User(Base):
    """Пользователь бота."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Настройки дайджеста
    digest_interval: Mapped[int] = mapped_column(Integer, default=24)  # часы
    digest_news_limit: Mapped[int] = mapped_column(Integer, default=20)  # лимит важных новостей
    last_digest_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Канал для отправки дайджестов
    digest_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    digest_thread_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    clusters: Mapped[list["Cluster"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Cluster(Base):
    """Тематический кластер каналов."""
    
    __tablename__ = "clusters"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="clusters")
    channels: Mapped[list["Channel"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")


class Channel(Base):
    """Telegram канал или группа."""
    
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clusters.id"), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    cluster: Mapped[Optional["Cluster"]] = relationship(back_populates="channels")


class DigestHistory(Base):
    """История отправленных дайджестов."""
    
    __tablename__ = "digest_history"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    
    content: Mapped[str] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProcessedMessage(Base):
    """Кэш обработанных сообщений (для экономии токенов)."""
    
    __tablename__ = "processed_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(Integer, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


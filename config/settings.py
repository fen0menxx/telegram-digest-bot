"""
Настройки приложения.

Загружает переменные окружения из .env файла.
"""

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

# Загружаем .env из корня проекта
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass
class Settings:
    """Настройки приложения."""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Telegram API (для Telethon userbot)
    API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Владелец бота (только он может использовать)
    OWNER_ID: int = int(os.getenv("OWNER_TELEGRAM_ID", "0"))
    
    # Пути
    DATA_DIR: Path = ROOT_DIR / "data"
    DB_PATH: Path = DATA_DIR / "digest.db"
    SESSION_PATH: Path = DATA_DIR / "userbot"
    
    def __post_init__(self):
        """Создаём директорию data если не существует."""
        self.DATA_DIR.mkdir(exist_ok=True)
    
    def validate(self) -> list[str]:
        """Проверяет обязательные настройки."""
        errors = []
        
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен")
        if not self.API_ID:
            errors.append("API_ID не установлен")
        if not self.API_HASH:
            errors.append("API_HASH не установлен")
        if not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY не установлен")
        if not self.OWNER_ID:
            errors.append("OWNER_ID не установлен")
        
        return errors


# Глобальный экземпляр настроек
settings = Settings()


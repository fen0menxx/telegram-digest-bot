"""
Одноразовый запуск генерации дайджестов (cron / Task Scheduler).

В отличие от src/main.py не запускает aiogram polling и APScheduler:
просто инициализирует БД + Telethon + бот, вызывает check_and_send_digests
с force=True и завершается.

Запуск:
    python make_digest.py            # обычный запуск (с антидублём 2ч)
    python make_digest.py --force    # принудительно, игнорируя антидубль

Антидубль: если последний успешный запуск был < MIN_INTERVAL_MINUTES
минут назад — выходим без работы. Защита от двойного срабатывания
триггеров Task Scheduler (например, OnLogon сразу после "пропущенного"
8:03).

Логи: data/digest_runs.log (ротация 10 MB, хранение 30 дней).
Маркер последнего запуска: data/last_digest_run.txt.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings

LAST_RUN_FILE = settings.DATA_DIR / "last_digest_run.txt"
RUN_LOG_FILE = settings.DATA_DIR / "digest_runs.log"
MIN_INTERVAL_MINUTES = 120  # антидубль: не запускаемся чаще раза в 2 часа


def setup_logging() -> None:
    """Логи в stdout + файл с ротацией."""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        RUN_LOG_FILE,
        rotation="10 MB",
        retention="30 days",
        level="INFO",
        encoding="utf-8",
    )


def check_anti_duplicate(force: bool) -> bool:
    """
    Returns True если можно запускать, False если слишком рано после
    предыдущего запуска.
    """
    if force:
        logger.info("Флаг --force: антидубль игнорируется")
        return True

    if not LAST_RUN_FILE.exists():
        return True

    try:
        last_str = LAST_RUN_FILE.read_text(encoding="utf-8").strip()
        last_run = datetime.fromisoformat(last_str)
    except (ValueError, OSError) as e:
        logger.warning(f"Не удалось прочитать {LAST_RUN_FILE.name}: {e} — продолжаем")
        return True

    diff = datetime.now() - last_run
    diff_min = int(diff.total_seconds() / 60)

    if diff < timedelta(minutes=MIN_INTERVAL_MINUTES):
        logger.info(
            f"Антидубль: прошло {diff_min} мин с последнего запуска "
            f"(минимум {MIN_INTERVAL_MINUTES} мин). Выход."
        )
        return False

    logger.info(f"Прошло {diff_min} мин с последнего запуска — продолжаем")
    return True


def update_last_run() -> None:
    """Записать время текущего успешного запуска."""
    try:
        LAST_RUN_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError as e:
        logger.warning(f"Не удалось записать {LAST_RUN_FILE.name}: {e}")


async def run(force: bool) -> int:
    """Основная логика. Возвращает код выхода (0 — успех)."""
    setup_logging()

    logger.info("=" * 60)
    logger.info(f"DIGEST RUN — {datetime.now():%Y-%m-%d %H:%M:%S}")
    logger.info("=" * 60)

    # Проверка обязательных настроек
    errors = settings.validate()
    if errors:
        for e in errors:
            logger.error(e)
        logger.error("Заполните .env и перезапустите")
        return 1

    # Антидубль
    if not check_anti_duplicate(force):
        return 0

    # БД
    from src.storage.database import init_db
    await init_db()

    # Pre-flight: проверяем валидность Telethon-сессии БЕЗ интерактивного
    # промпта. Если init_client попадёт на невалидную сессию, он попросит
    # input() — а в Task Scheduler нет stdin, задача зависнет.
    from telethon import TelegramClient as _TC
    _preflight = _TC(str(settings.SESSION_PATH), settings.API_ID, settings.API_HASH)
    await _preflight.connect()
    _authorized = await _preflight.is_user_authorized()
    await _preflight.disconnect()
    if not _authorized:
        logger.error(
            "Telethon-сессия недействительна или отсутствует. "
            "Запустите вручную: python -m src.main auth"
        )
        return 3

    # Telethon (использует существующую сессию data/userbot.session)
    from src.userbot.client import init_client, disconnect_client
    await init_client()

    # aiogram Bot — только для отправки сообщений, без polling
    from src.bot.bot import create_bot
    bot = create_bot()

    try:
        from src.scheduler.tasks import set_bot, check_and_send_digests
        set_bot(bot)

        # force=True — игнорируем user.digest_interval, расписанием
        # управляет Task Scheduler снаружи
        await check_and_send_digests(force=True)

        update_last_run()
        logger.success("Запуск завершён успешно")
        return 0
    except Exception as e:
        logger.exception(f"Ошибка во время выполнения: {e}")
        return 2
    finally:
        await disconnect_client()
        await bot.session.close()


def main() -> None:
    force = "--force" in sys.argv
    code = asyncio.run(run(force=force))
    sys.exit(code)


if __name__ == "__main__":
    main()

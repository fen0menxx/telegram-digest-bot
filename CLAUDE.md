# CLAUDE.md — инструкции для Claude Code

## О проекте

Telegram Digest Bot — бот для автоматического создания AI-дайджестов из Telegram-каналов.

**Архитектура:** одно приложение, два режима запуска:
1. **Интерактивный** (`src/main.py`) — aiogram polling + APScheduler, бот живёт постоянно, пользователь управляет через кнопки в Telegram
2. **Cron** (`make_digest.py`) — одноразовый запуск для Windows Task Scheduler: собрал дайджест → отправил → вышел

Обе точки входа используют общую БД (`data/digest.db`) и общую Telethon-сессию (`data/userbot.session`), не конфликтуют между собой.

## Структура проекта

```
Бот ТГ дайджест курсор/
├── src/
│   ├── main.py                 # Интерактивный бот (polling)
│   ├── ai/
│   │   ├── prompts.py
│   │   └── summarizer.py       # OpenAI суммаризация
│   ├── bot/
│   │   ├── bot.py              # create_bot, create_dispatcher
│   │   ├── keyboards.py
│   │   ├── middleware.py       # OwnerMiddleware (только владелец может пользоваться)
│   │   ├── states.py
│   │   └── handlers/           # старт, настройки, дайджест
│   ├── scheduler/
│   │   └── tasks.py            # check_and_send_digests(force=False)
│   ├── storage/
│   │   ├── database.py         # SQLAlchemy async + aiosqlite
│   │   └── models.py           # User, Cluster, Channel, DigestHistory, MessageCache
│   ├── userbot/
│   │   ├── client.py           # Telethon, init_client()
│   │   ├── channels.py
│   │   └── messages.py         # get_messages_from_channels
│   └── utils/
│       └── digest_sender.py    # filter_cached, save_backup, send_to_user_or_channel
│
├── config/
│   └── settings.py             # .env loader, Settings dataclass, validate()
│
├── data/                       # ⚠️ в .gitignore — содержит секреты
│   ├── digest.db               # SQLite основная БД
│   ├── bot.db                  # legacy (можно игнорировать)
│   ├── bot.log                 # лог интерактивного режима
│   ├── digest_runs.log         # лог cron-режима (ротация 10 MB, 30 дней)
│   ├── last_digest_run.txt     # маркер последнего cron-запуска (для антидубля)
│   ├── userbot.session         # Telethon-сессия (КРИТИЧНО, не коммитить!)
│   ├── digest_backups/         # бэкапы дайджестов (.txt) после генерации AI
│   └── digest_inputs/          # входные данные AI (для дебага)
│
├── tests/
│
├── .env                        # ⚠️ не в git
├── requirements.txt
├── README.md
├── CLAUDE.md                   # этот файл
├── CONTINUITY.md               # журнал изменений
│
├── start_bot.bat               # запуск интерактивного режима
├── run_digest.bat              # запуск cron-режима (для Task Scheduler)
├── make_digest.py              # cron-точка входа
├── register_tasks.ps1          # регистрация 3 задач в Windows Task Scheduler
│
├── clear_cache.py              # утилита очистки кэша сообщений
├── clear_session.py            # утилита удаления Telethon-сессии (для re-auth)
├── migrate_db.py               # миграция legacy bot.db → digest.db
└── git_push.py                 # утилита для git push
```

## Команды запуска

```powershell
# Активация venv
.venv\Scripts\activate

# Интерактивный режим (бот с polling)
python -m src.main
# или
.\start_bot.bat

# Авторизация Telethon (один раз, либо после revoke)
python -m src.main auth

# Cron-режим (одноразовый запуск, антидубль 2ч)
python make_digest.py

# Cron-режим без антидубля
python make_digest.py --force

# Установить расписание Task Scheduler (3 задачи)
powershell -ExecutionPolicy Bypass -File register_tasks.ps1

# Удалить расписание
powershell -ExecutionPolicy Bypass -File register_tasks.ps1 -Unregister
```

## Ключевые зависимости (из requirements.txt)

- **aiogram >= 3.4** — Telegram Bot API
- **telethon >= 1.34** — userbot для чтения каналов
- **sqlalchemy >= 2.0** + **aiosqlite >= 0.19** — async ORM
- **openai >= 1.12** — суммаризация
- **apscheduler >= 3.10** — внутренний планировщик (только в интерактивном режиме)
- **python-dotenv >= 1.0**
- **loguru >= 0.7**
- **cryptg >= 0.4** — ускорение Telethon

## Переменные окружения (.env)

```
BOT_TOKEN=...                    # от @BotFather
TELEGRAM_API_ID=...              # с https://my.telegram.org
TELEGRAM_API_HASH=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini         # опционально, дефолт gpt-4o-mini
OWNER_TELEGRAM_ID=...            # ваш Telegram ID — только владелец может управлять ботом
```

Валидация в `config/settings.py:validate()` — отсутствие любого из `BOT_TOKEN / API_ID / API_HASH / OPENAI_API_KEY / OWNER_ID` приведёт к выходу с ошибкой.

## Логика дайджеста (`src/scheduler/tasks.py`)

`check_and_send_digests(force=False)`:
- Получает всех `is_active=True` пользователей
- Для каждого вызывает `_process_user_digest(user, now, force)`

`_process_user_digest(user, now, force=False)`:
- **Когда отправлять:**
  - `force=True` → всегда (cron-режим, расписание управляется снаружи)
  - `last_digest_at is None` → первый раз
  - `last_digest_at + digest_interval <= now` → штатная проверка
- **Период сбора:** «вчера 00:00 — сейчас» (catch-up до 2 дней, защита от долгого простоя)
- **Кластеры:** для каждого `Cluster` пользователя — отдельный дайджест
- **Кэш:** `MessageCache` фильтрует уже обработанные сообщения; кэширование происходит **только после** успешной отправки в Telegram (если падение на отправке — следующий запуск повторит)
- **Бэкап:** `data/digest_backups/{timestamp}_{cluster}.txt` сохраняется СРАЗУ после генерации AI, до отправки

## Автоматизация (Task Scheduler)

### 3 задачи

| Имя | Триггер | Назначение |
|---|---|---|
| `TG_Digest_Morning` | ежедневно 08:03 | утренний выпуск |
| `TG_Digest_Evening` | ежедневно 19:03 | вечерний выпуск |
| `TG_Digest_OnLogon` | при входе в Windows + 1 мин | подхват пропущенных |

### Опции каждой задачи

- `LogonType Interactive` (без сохранения пароля)
- `RunLevel Limited` (обычный пользователь)
- `StartWhenAvailable` (выполнить пропущенное при первой возможности)
- `WakeToRun` (разбудить ПК из режима сна)
- `RestartCount 3 / RestartInterval 5min` (3 повтора при сбое)
- `MultipleInstances IgnoreNew` (параллельный запуск невозможен)
- `ExecutionTimeLimit 30min`

### Антидубль

Внутри `make_digest.py` — проверка `data/last_digest_run.txt`. Если последний запуск был < 120 минут назад — выход без работы. Защита от двойного срабатывания триггеров (например, OnLogon сразу после пропущенного утреннего слота).

Флаг `--force` игнорирует антидубль (используется при ручном тестировании).

### Pre-flight проверка Telethon-сессии

`make_digest.py` перед `init_client()` делает быструю проверку `is_user_authorized()`. Если сессия невалидна — выход с кодом 3 и сообщением «запустите `python -m src.main auth`». Это защищает от зависания на 30 мин (Task Scheduler не имеет stdin, а `init_client` при невалидной сессии вызывает `input()`).

## Важно при разработке

- Код и комментарии на русском языке
- Обе точки входа (`main.py`, `make_digest.py`) используют общую БД и сессию — не должны запускаться одновременно
- `data/userbot.session` — критичный секрет, никогда не коммитить (в `.gitignore` уже добавлено `*.session`)
- `.env` — критичный секрет, никогда не коммитить
- Время в БД хранится в UTC (`datetime.utcnow()`)
- Параметр `force` в `tasks.py` — обратно-совместимое расширение, default False, не ломает существующий код
- При изменении расписания Task Scheduler — править значения `-At "08:03"` / `-At "19:03"` в `register_tasks.ps1`, потом перезапустить скрипт

## Ограничения архитектуры

- **Один владелец на инсталляцию** (`OWNER_TELEGRAM_ID`) — middleware блокирует всех остальных
- **Telethon-сессия привязана к API_ID** — при смене API_ID нужна повторная авторизация
- **Cron-режим не учитывает `digest_interval` пользователя** (по дизайну — расписанием управляет Task Scheduler)
- **Канальные посты с медиа** — Telethon отдаёт только текстовое содержимое (caption), сами медиа не скачиваются

## Где смотреть при отладке

| Вопрос | Где |
|---|---|
| «Был ли запуск сегодня?» | `data/digest_runs.log`, `data/last_digest_run.txt` |
| «Что отправилось в дайджесте?» | `data/digest_backups/*.txt` (свежие — внизу) |
| «Что AI получил на вход?» | `data/digest_inputs/*.txt` |
| «Зарегистрированы ли задачи Windows?» | `Get-ScheduledTask -TaskName "TG_Digest_*"` |
| «Когда следующий запуск?» | `(Get-ScheduledTaskInfo TG_Digest_Morning).NextRunTime` |

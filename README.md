# Telegram Digest Bot 📰

Бот для автоматического создания дайджестов из Telegram-каналов с помощью AI.

## Возможности

- 📁 **Кластеры** — группировка каналов по тематикам
- 📊 **AI-дайджесты** — умная суммаризация новостей через OpenAI
- ⏰ **Автоматические дайджесты** — по расписанию
- 🔗 **Кликабельные ссылки** — на оригинальные сообщения
- 💾 **Кэширование** — экономия токенов AI
- 📢 **Отправка в канал** — дайджесты в ваш Telegram-канал

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/fen0menxx/telegram-digest-bot.git
cd telegram-digest-bot
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте `.env` файл:
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_from_botfather

# Telegram API (https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Owner
OWNER_TELEGRAM_ID=your_telegram_id
```

5. Авторизуйте userbot:
```bash
python -m src.main auth
```

6. Запустите бота:
```bash
python -m src.main
```

## Использование

1. Напишите боту `/start`
2. Нажмите "🔄 Сканировать каналы" для поиска ваших каналов
3. Создайте кластеры и добавьте в них каналы
4. Запросите дайджест через "📊 Дайджест"

## Структура проекта

```
├── src/
│   ├── ai/           # AI-суммаризация (OpenAI)
│   ├── bot/          # Telegram бот (aiogram)
│   ├── scheduler/    # Планировщик задач
│   ├── storage/      # База данных (SQLite + SQLAlchemy)
│   ├── userbot/      # Telethon клиент
│   └── utils/        # Утилиты
├── config/           # Настройки
├── data/             # Данные (игнорируется git)
└── requirements.txt
```

## Технологии

- **aiogram 3** — Telegram Bot API
- **Telethon** — Telegram Userbot API
- **OpenAI GPT** — AI-суммаризация
- **SQLAlchemy + aiosqlite** — асинхронная БД
- **APScheduler** — планировщик задач

## Автоматический запуск (Windows Task Scheduler)

Если бот нужен только для генерации дайджестов по расписанию (без интерактивного UI), можно запускать его как разовую задачу через Task Scheduler.

### Что устанавливается

3 задачи, все запускают `run_digest.bat` → `python make_digest.py`:

| Задача | Триггер | Назначение |
|---|---|---|
| `TG_Digest_Morning` | ежедневно 08:03 | утренний дайджест |
| `TG_Digest_Evening` | ежедневно 19:03 | вечерний дайджест |
| `TG_Digest_OnLogon` | при входе в Windows (+1 мин) | подхват пропущенных запусков |

Все задачи:
- работают только когда вы залогинены (без сохранения пароля)
- выполняют пропущенный запуск при первой возможности (`-StartWhenAvailable`)
- будят ПК из режима сна (`-WakeToRun`)
- перезапускаются 3 раза с интервалом 5 мин при сбое

**Антидубль:** внутри `make_digest.py` есть проверка: если последний запуск был < 2 часов назад — выходит без работы. Это защищает от двойного срабатывания (например, OnLogon сразу после пропущенного утреннего слота).

### Установка задач

Один раз, в PowerShell в папке проекта:

```powershell
powershell -ExecutionPolicy Bypass -File register_tasks.ps1
```

### Удаление задач

```powershell
powershell -ExecutionPolicy Bypass -File register_tasks.ps1 -Unregister
```

### Запуск вручную

```bash
# Обычный запуск (с антидублём 2ч)
python make_digest.py

# Принудительно, игнорируя антидубль
python make_digest.py --force
```

### Логи

- `data/digest_runs.log` — лог запусков (ротация 10 MB, хранение 30 дней)
- `data/last_digest_run.txt` — маркер времени последнего успешного запуска

### Интерактивный режим — без изменений

`start_bot.bat` и `python -m src.main` продолжают работать как раньше. Cron-режим и интерактивный режим не конфликтуют (используют общую БД и сессию Telethon).

## Лицензия

MIT






























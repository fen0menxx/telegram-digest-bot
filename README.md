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

## Лицензия

MIT


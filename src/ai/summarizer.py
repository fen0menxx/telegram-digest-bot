"""
Суммаризация сообщений через OpenAI.

Генерирует дайджест из списка сообщений.
"""

import re
import sys
from pathlib import Path
from datetime import datetime

from openai import AsyncOpenAI
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.ai.prompts import DIGEST_SYSTEM_PROMPT, DIGEST_USER_PROMPT
from src.userbot.messages import MessageInfo

# Папка для логирования входных данных
DIGEST_INPUTS_DIR = Path(__file__).parent.parent.parent / "data" / "digest_inputs"
DIGEST_INPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Клиент OpenAI
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def sanitize_html_for_telegram(text: str) -> str:
    """
    Очищает HTML для совместимости с Telegram.
    
    Telegram поддерживает только: <b>, <i>, <a>, <code>, <pre>, <u>, <s>
    """
    # Удаляем неподдерживаемые теги
    unsupported_tags = [
        r'<br\s*/?>', r'<hr\s*/?>', r'<p\s*/?>', r'</p>',
        r'<div[^>]*>', r'</div>', r'<span[^>]*>', r'</span>',
        r'<h[1-6][^>]*>', r'</h[1-6]>',
    ]
    
    for tag in unsupported_tags:
        text = re.sub(tag, '\n', text, flags=re.IGNORECASE)
    
    # Экранируем & в URL (но не &amp; и т.д.)
    text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', text)
    
    # Убираем множественные переносы строк
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


async def summarize_messages(
    messages: list[MessageInfo],
    cluster_name: str,
    news_limit: int = 20,
) -> str:
    """
    Генерирует дайджест из списка сообщений.
    
    Args:
        messages: Список сообщений
        cluster_name: Название кластера
        news_limit: Максимум важных новостей
    
    Returns:
        HTML-текст дайджеста для Telegram
    """
    if not messages:
        return f"<b>📰 Дайджест: {cluster_name}</b>\n\nНет новых сообщений."
    
    # Формируем текст сообщений для AI
    messages_text = ""
    channels_set = set()
    
    for i, msg in enumerate(messages, 1):
        channels_set.add(msg.channel_title)
        messages_text += f"""
--- Сообщение #{i} ---
Канал: {msg.channel_title}
Дата: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}
Ссылка: {msg.link}
Просмотры: {msg.views or 'N/A'}
Текст:
{msg.text}
"""
    
    # Определяем период
    dates = [msg.date for msg in messages]
    period_start = min(dates).strftime('%d.%m.%Y')
    period_end = max(dates).strftime('%d.%m.%Y')
    
    # Логируем входные данные
    input_log = f"""=== ВХОДНЫЕ ДАННЫЕ ДЛЯ AI ===
Время: {datetime.now().isoformat()}
Кластер: {cluster_name}
Период: {period_start} — {period_end}
Сообщений: {len(messages)}
Каналов: {len(channels_set)}
=====================================

=== СПИСОК СООБЩЕНИЙ ===
{messages_text}
"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_file = DIGEST_INPUTS_DIR / f"{timestamp}_{cluster_name}.txt"
    input_file.write_text(input_log, encoding="utf-8")
    
    logger.info(f"Генерация дайджеста: {cluster_name}, {len(messages)} сообщений, {len(channels_set)} каналов")
    logger.info(f"📝 Входные данные сохранены: {input_file.name}")
    
    # Формируем промпт
    user_prompt = DIGEST_USER_PROMPT.format(
        cluster_name=cluster_name,
        period_start=period_start,
        period_end=period_end,
        message_count=len(messages),
        channel_count=len(channels_set),
        news_limit=news_limit,
        messages=messages_text,
    )
    
    # Запрос к OpenAI
    response = await openai_client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4000,
    )
    
    # Логируем использование токенов
    usage = response.usage
    logger.info(f"OpenAI usage: {usage.prompt_tokens} prompt, {usage.completion_tokens} completion, {usage.total_tokens} total")
    
    # Получаем и очищаем ответ
    digest_text = response.choices[0].message.content
    digest_text = sanitize_html_for_telegram(digest_text)
    
    return digest_text






























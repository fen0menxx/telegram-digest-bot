"""
Клавиатуры для бота.

Reply-клавиатуры (внизу экрана) для основного интерфейса.
Inline-клавиатуры используются только для выбора из списков.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# =============================================================================
# REPLY КЛАВИАТУРЫ (внизу экрана)
# =============================================================================

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню — Reply-клавиатура 2x2."""
    builder = ReplyKeyboardBuilder()
    
    # Ряд 1: Дайджест | Кластеры
    builder.row(
        KeyboardButton(text="📊 Дайджест"),
        KeyboardButton(text="📁 Кластеры"),
    )
    # Ряд 2: Сканировать | Настройки
    builder.row(
        KeyboardButton(text="🔄 Сканировать\nканалы"),
        KeyboardButton(text="⚙️ Настройки"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_clusters_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню кластеров — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="➕ Создать кластер"),
    )
    builder.row(
        KeyboardButton(text="🔙 Назад"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_cluster_actions_keyboard() -> ReplyKeyboardMarkup:
    """Меню действий с кластером — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="✏️ Редактировать каналы"),
        KeyboardButton(text="📋 Управление каналами"),
    )
    builder.row(
        KeyboardButton(text="✏️ Переименовать"),
        KeyboardButton(text="🗑 Удалить кластер"),
    )
    builder.row(
        KeyboardButton(text="🔙 К кластерам"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_digest_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню дайджеста — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="📊 Все кластеры"),
    )
    builder.row(
        KeyboardButton(text="🔙 Назад"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_digest_period_reply_keyboard() -> ReplyKeyboardMarkup:
    """Выбор периода — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="📅 За сегодня"),
        KeyboardButton(text="📅 За вчера"),
    )
    builder.row(
        KeyboardButton(text="📅 За 2 дня"),
        KeyboardButton(text="📅 За 3 дня"),
    )
    builder.row(
        KeyboardButton(text="📅 За 7 дней"),
        KeyboardButton(text="🔄 С последнего дайджеста"),
    )
    builder.row(
        KeyboardButton(text="🔙 Назад"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_settings_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню настроек — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="⏰ Интервал дайджестов"),
    )
    builder.row(
        KeyboardButton(text="📰 Лимит важных новостей"),
    )
    builder.row(
        KeyboardButton(text="📢 Канал для дайджестов"),
    )
    builder.row(
        KeyboardButton(text="🗑 Очистить историю дайджестов"),
    )
    builder.row(
        KeyboardButton(text="🔙 Назад"),
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_back_keyboard_reply() -> ReplyKeyboardMarkup:
    """Кнопка назад — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔙 Назад"))
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка отмены — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def get_confirm_delete_reply_keyboard() -> ReplyKeyboardMarkup:
    """Подтверждение удаления — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Да, удалить"),
        KeyboardButton(text="❌ Отмена"),
    )
    return builder.as_markup(resize_keyboard=True)


def get_channels_save_keyboard() -> ReplyKeyboardMarkup:
    """Кнопки сохранения/отмены для каналов — Reply-клавиатура."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔍 Поиск"),
    )
    builder.row(
        KeyboardButton(text="💾 Сохранить"),
        KeyboardButton(text="❌ Отмена"),
    )
    return builder.as_markup(resize_keyboard=True)


# =============================================================================
# INLINE КЛАВИАТУРЫ (для списков и выбора)
# =============================================================================

def get_clusters_keyboard(clusters: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Список кластеров — Inline для выбора."""
    builder = InlineKeyboardBuilder()
    
    for cluster_id, name in clusters:
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {name}",
                callback_data=f"cluster:{cluster_id}",
            )
        )
    
    return builder.as_markup()


def get_digest_clusters_keyboard(clusters: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Выбор кластера для дайджеста — Inline."""
    builder = InlineKeyboardBuilder()
    
    for cluster_id, name in clusters:
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {name}",
                callback_data=f"digest_cluster:{cluster_id}",
            )
        )
    
    return builder.as_markup()


def get_channels_keyboard(
    channels: list[tuple[int, str, bool]],
    cluster_id: int,
    page: int = 0,
    per_page: int = 10,
    search_query: str = "",
) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора каналов для кластера — Inline.
    
    Args:
        channels: Список (channel_id, title, is_selected)
        cluster_id: ID кластера
        page: Текущая страница
        per_page: Каналов на странице
        search_query: Поисковый запрос
    """
    builder = InlineKeyboardBuilder()
    
    # Пагинация
    start = page * per_page
    end = start + per_page
    page_channels = channels[start:end]
    
    for ch_id, title, is_selected in page_channels:
        mark = "✅" if is_selected else "⬜"
        # Сокращаем название если длинное
        display_title = title[:30] + "..." if len(title) > 30 else title
        builder.row(
            InlineKeyboardButton(
                text=f"{mark} {display_title}",
                callback_data=f"ch_toggle:{cluster_id}:{ch_id}:{page}",
            )
        )
    
    # Навигация по страницам
    nav_buttons = []
    total_pages = (len(channels) + per_page - 1) // per_page if channels else 1
    
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"ch_page:{cluster_id}:{page - 1}")
        )
    
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"ch_page:{cluster_id}:{page + 1}")
        )
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Кнопка поиска (если есть активный поиск)
    if search_query:
        builder.row(
            InlineKeyboardButton(
                text=f"🔍 {search_query[:15]}...",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="❌ Сбросить",
                callback_data=f"ch_reset_search:{cluster_id}",
            ),
        )
    
    return builder.as_markup()


def get_manage_channels_keyboard(
    channels: list[tuple[int, str]],
    cluster_id: int,
) -> InlineKeyboardMarkup:
    """
    Клавиатура управления каналами в кластере (удаление) — Inline.
    
    Args:
        channels: Список (channel_id, title)
        cluster_id: ID кластера
    """
    builder = InlineKeyboardBuilder()
    
    for ch_id, title in channels:
        display_title = title[:25] + "..." if len(title) > 25 else title
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 {display_title}",
                callback_data=f"ch_remove:{cluster_id}:{ch_id}",
            )
        )
    
    return builder.as_markup()


def get_interval_keyboard() -> InlineKeyboardMarkup:
    """Выбор интервала дайджестов — Inline."""
    builder = InlineKeyboardBuilder()
    
    intervals = [
        ("Каждые 6 часов", 6),
        ("Каждые 12 часов", 12),
        ("Раз в день", 24),
        ("Раз в 2 дня", 48),
        ("Раз в неделю", 168),
    ]
    
    for label, hours in intervals:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"set_interval:{hours}",
            )
        )
    
    return builder.as_markup()


def get_digest_news_limit_keyboard() -> InlineKeyboardMarkup:
    """Выбор лимита важных новостей — Inline."""
    builder = InlineKeyboardBuilder()
    
    limits = [15, 20, 25, 30, 35, 40, 50]
    
    for limit in limits:
        builder.row(
            InlineKeyboardButton(
                text=f"До {limit} новостей",
                callback_data=f"set_news_limit:{limit}",
            )
        )
    
    return builder.as_markup()


# =============================================================================
# LEGACY (для совместимости, если где-то используются)
# =============================================================================

def get_main_menu_keyboard_inline() -> InlineKeyboardMarkup:
    """Главное меню — Inline (legacy)."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📁 Кластеры", callback_data="clusters"),
        InlineKeyboardButton(text="📊 Дайджест", callback_data="digest"),
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Сканировать каналы", callback_data="scan_channels"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
    )
    
    return builder.as_markup()


def get_back_keyboard(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    """Кнопка "Назад" — Inline (legacy)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data),
    )
    return builder.as_markup()


def get_cluster_menu_keyboard(cluster_id: int) -> InlineKeyboardMarkup:
    """Меню кластера — Inline (legacy, для callback навигации)."""
    builder = InlineKeyboardBuilder()
    # Пустая клавиатура, т.к. используем Reply
    return builder.as_markup()


def get_confirm_delete_keyboard(cluster_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления кластера — Inline (legacy)."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"cluster_delete_confirm:{cluster_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"cluster:{cluster_id}",
        ),
    )
    
    return builder.as_markup()


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек — Inline (legacy)."""
    builder = InlineKeyboardBuilder()
    return builder.as_markup()


def get_digest_period_keyboard(cluster_param: str) -> InlineKeyboardMarkup:
    """Выбор периода для дайджеста — Inline (legacy)."""
    builder = InlineKeyboardBuilder()
    
    periods = [
        ("📅 За сегодня", 1),
        ("📅 За вчера", 24),
        ("📅 За 2 дня", 48),
        ("📅 За 3 дня", 72),
        ("📅 За 7 дней", 168),
        ("🔄 С последнего дайджеста", 0),
    ]
    
    for label, hours in periods:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"digest_period:{cluster_param}:{hours}",
            )
        )
    
    return builder.as_markup()

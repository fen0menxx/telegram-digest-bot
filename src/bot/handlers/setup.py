"""
Обработчики настройки кластеров и каналов.

Создание, редактирование, удаление кластеров.
Добавление каналов в кластеры.
Использует Reply-клавиатуры.
"""

import sys
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from loguru import logger

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.bot.keyboards import (
    get_main_menu_keyboard,
    get_clusters_menu_keyboard,
    get_cluster_actions_keyboard,
    get_clusters_keyboard,
    get_channels_keyboard,
    get_manage_channels_keyboard,
    get_cancel_keyboard,
    get_confirm_delete_reply_keyboard,
    get_channels_save_keyboard,
    get_back_keyboard_reply,
)
from src.bot.states import MenuStates, InputStates
from src.storage.database import get_session
from src.storage.models import Cluster, Channel
from src.userbot.channels import scan_user_channels

router = Router(name="setup")


# =============================================================================
# КЛАСТЕРЫ — ГЛАВНОЕ МЕНЮ
# =============================================================================

@router.message(F.text == "📁 Кластеры")
async def msg_clusters(message: Message, state: FSMContext) -> None:
    """Переход в меню кластеров."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.user_id == user_id)
        )
        clusters = result.scalars().all()
    
    clusters_data = [(c.id, c.name) for c in clusters]
    
    await state.set_state(MenuStates.clusters_list)
    
    if not clusters_data:
        await message.answer(
            "📁 <b>Кластеры</b>\n\n"
            "У вас пока нет кластеров.\n"
            "Создайте первый кластер для группировки каналов.",
            reply_markup=get_clusters_menu_keyboard(),
        )
    else:
        await message.answer(
            "📁 <b>Ваши кластеры:</b>\n\n"
            "Выберите кластер из списка ниже:",
            reply_markup=get_clusters_menu_keyboard(),
        )
        await message.answer(
            "👇 <b>Кластеры:</b>",
            reply_markup=get_clusters_keyboard(clusters_data),
        )


@router.message(F.text == "➕ Создать кластер")
async def msg_cluster_create(message: Message, state: FSMContext) -> None:
    """Создание нового кластера."""
    await state.set_state(InputStates.waiting_cluster_name)
    await message.answer(
        "📝 <b>Создание кластера</b>\n\n"
        "Введите название для нового кластера:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(InputStates.waiting_cluster_name)
async def process_cluster_name(message: Message, state: FSMContext) -> None:
    """Обработка названия кластера."""
    if message.text == "❌ Отмена":
        await state.set_state(MenuStates.clusters_list)
        await message.answer(
            "❌ Создание отменено.",
            reply_markup=get_clusters_menu_keyboard(),
        )
        return
    
    name = message.text.strip()
    user_id = message.from_user.id
    
    if len(name) < 2:
        await message.answer("❌ Название слишком короткое. Минимум 2 символа.")
        return
    
    if len(name) > 100:
        await message.answer("❌ Название слишком длинное. Максимум 100 символов.")
        return
    
    async with get_session() as session:
        cluster = Cluster(user_id=user_id, name=name)
        session.add(cluster)
        await session.commit()
        cluster_id = cluster.id
    
    await state.update_data(cluster_id=cluster_id)
    await state.set_state(MenuStates.cluster_view)
    
    await message.answer(
        f"✅ Кластер <b>{name}</b> создан!\n\n"
        "Теперь добавьте в него каналы.",
        reply_markup=get_cluster_actions_keyboard(),
    )


# =============================================================================
# ПРОСМОТР КЛАСТЕРА
# =============================================================================

@router.callback_query(F.data.startswith("cluster:"))
async def cb_cluster_view(callback: CallbackQuery, state: FSMContext) -> None:
    """Просмотр кластера (выбор из inline-списка)."""
    cluster_id = int(callback.data.split(":")[1])
    
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        
        if not cluster:
            await callback.answer("Кластер не найден", show_alert=True)
            return
        
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster_id)
        )
        channels = result.scalars().all()
    
    channels_text = ""
    if channels:
        channels_text = "\n\n📢 <b>Каналы:</b>\n"
        for ch in channels[:10]:  # Показываем первые 10
            channels_text += f"• {ch.title}\n"
        if len(channels) > 10:
            channels_text += f"... и ещё {len(channels) - 10}"
    else:
        channels_text = "\n\n<i>Каналы не добавлены</i>"
    
    await state.update_data(cluster_id=cluster_id)
    await state.set_state(MenuStates.cluster_view)
    
    await callback.message.answer(
        f"📁 <b>Кластер: {cluster.name}</b>{channels_text}",
        reply_markup=get_cluster_actions_keyboard(),
    )
    await callback.answer()


@router.message(F.text == "🔙 К кластерам")
async def msg_back_to_clusters(message: Message, state: FSMContext) -> None:
    """Назад к списку кластеров."""
    await msg_clusters(message, state)


# =============================================================================
# ПЕРЕИМЕНОВАНИЕ КЛАСТЕРА
# =============================================================================

@router.message(F.text == "✏️ Переименовать", MenuStates.cluster_view)
async def msg_cluster_rename(message: Message, state: FSMContext) -> None:
    """Переименование кластера."""
    await state.set_state(InputStates.waiting_cluster_rename)
    await message.answer(
        "✏️ <b>Переименование кластера</b>\n\n"
        "Введите новое название:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(InputStates.waiting_cluster_rename)
async def process_cluster_rename(message: Message, state: FSMContext) -> None:
    """Обработка нового названия кластера."""
    if message.text == "❌ Отмена":
        await state.set_state(MenuStates.cluster_view)
        await message.answer(
            "❌ Переименование отменено.",
            reply_markup=get_cluster_actions_keyboard(),
        )
        return
    
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    new_name = message.text.strip()
    
    if len(new_name) < 2:
        await message.answer("❌ Название слишком короткое. Минимум 2 символа.")
        return
    
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        
        if cluster:
            old_name = cluster.name
            cluster.name = new_name
            await session.commit()
    
    await state.set_state(MenuStates.cluster_view)
    
    await message.answer(
        f"✅ Кластер переименован: <b>{old_name}</b> → <b>{new_name}</b>",
        reply_markup=get_cluster_actions_keyboard(),
    )


# =============================================================================
# УДАЛЕНИЕ КЛАСТЕРА
# =============================================================================

@router.message(F.text == "🗑 Удалить кластер", MenuStates.cluster_view)
async def msg_cluster_delete(message: Message, state: FSMContext) -> None:
    """Запрос подтверждения удаления."""
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
    
    if not cluster:
        await message.answer("Кластер не найден")
        return
    
    await state.set_state(InputStates.waiting_confirm_delete)
    
    await message.answer(
        f"🗑 <b>Удаление кластера</b>\n\n"
        f"Вы уверены, что хотите удалить кластер <b>{cluster.name}</b>?\n\n"
        "⚠️ Все каналы будут откреплены от кластера.",
        reply_markup=get_confirm_delete_reply_keyboard(),
    )


@router.message(InputStates.waiting_confirm_delete)
async def process_delete_confirm(message: Message, state: FSMContext) -> None:
    """Подтверждение удаления."""
    if message.text == "❌ Отмена":
        await state.set_state(MenuStates.cluster_view)
        await message.answer(
            "❌ Удаление отменено.",
            reply_markup=get_cluster_actions_keyboard(),
        )
        return
    
    if message.text == "✅ Да, удалить":
        data = await state.get_data()
        cluster_id = data.get("cluster_id")
        
        async with get_session() as session:
            result = await session.execute(
                select(Cluster).where(Cluster.id == cluster_id)
            )
            cluster = result.scalar_one_or_none()
            
            if cluster:
                name = cluster.name
                await session.delete(cluster)
                await session.commit()
        
        await state.set_state(MenuStates.clusters_list)
        
        await message.answer(
            f"✅ Кластер <b>{name}</b> удалён.",
            reply_markup=get_clusters_menu_keyboard(),
        )
    else:
        await message.answer("Нажмите одну из кнопок ниже.")


# =============================================================================
# РЕДАКТИРОВАНИЕ КАНАЛОВ
# =============================================================================

@router.message(F.text == "✏️ Редактировать каналы", MenuStates.cluster_view)
async def msg_cluster_edit(message: Message, state: FSMContext) -> None:
    """Редактирование каналов кластера."""
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    user_id = message.from_user.id
    
    # Получаем все доступные каналы (только свободные или уже в этом кластере)
    async with get_session() as session:
        # Каналы уже в этом кластере
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster_id)
        )
        cluster_channels = {ch.telegram_id for ch in result.scalars().all()}
        
        # Все каналы пользователя (назначенные)
        result = await session.execute(
            select(Channel).where(Channel.cluster_id != None)
        )
        all_assigned = {ch.telegram_id for ch in result.scalars().all()}
    
    # Сканируем каналы пользователя
    scanned = await scan_user_channels()
    
    # Фильтруем: показываем только свободные или уже в этом кластере
    available = []
    for ch in scanned:
        if ch.id in cluster_channels:
            # Уже в этом кластере — показываем с галочкой
            available.append((ch.id, ch.title, True))
        elif ch.id not in all_assigned:
            # Свободный канал
            available.append((ch.id, ch.title, False))
    
    # Инициализируем выбранные каналы
    await state.update_data(
        selected_channels=list(cluster_channels),
        search_query="",
    )
    await state.set_state(MenuStates.cluster_edit_channels)
    
    if not available:
        await message.answer(
            "📢 <b>Нет доступных каналов</b>\n\n"
            "Все ваши каналы уже добавлены в другие кластеры.\n"
            "Сначала удалите их из других кластеров.",
            reply_markup=get_cluster_actions_keyboard(),
        )
        await state.set_state(MenuStates.cluster_view)
        return
    
    await message.answer(
        "📢 <b>Выберите каналы для кластера:</b>\n\n"
        f"Доступно: {len(available)} каналов\n\n"
        "Нажимайте на каналы в списке ниже, чтобы выбрать/отменить:",
        reply_markup=get_channels_save_keyboard(),
    )
    await message.answer(
        "👇 <b>Каналы:</b>",
        reply_markup=get_channels_keyboard(available, cluster_id, page=0),
    )


@router.callback_query(F.data.startswith("ch_toggle:"))
async def cb_channel_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключение выбора канала."""
    parts = callback.data.split(":")
    cluster_id = int(parts[1])
    channel_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    
    data = await state.get_data()
    selected = set(data.get("selected_channels", []))
    search_query = data.get("search_query", "")
    
    # Переключаем
    if channel_id in selected:
        selected.discard(channel_id)
    else:
        selected.add(channel_id)
    
    await state.update_data(selected_channels=list(selected))
    
    # Перестраиваем клавиатуру
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id != None)
        )
        all_assigned = {ch.telegram_id for ch in result.scalars().all()}
    
    scanned = await scan_user_channels()
    
    available = []
    for ch in scanned:
        if search_query and search_query.lower() not in ch.title.lower():
            continue
        
        is_selected = ch.id in selected
        
        if ch.id in selected or ch.id not in all_assigned:
            available.append((ch.id, ch.title, is_selected))
    
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_channels_keyboard(available, cluster_id, page=page, search_query=search_query),
        )
    except TelegramBadRequest:
        pass  # Клавиатура не изменилась
    
    await callback.answer()


@router.callback_query(F.data.startswith("ch_page:"))
async def cb_channel_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключение страницы каналов."""
    parts = callback.data.split(":")
    cluster_id = int(parts[1])
    page = int(parts[2])
    
    data = await state.get_data()
    selected = set(data.get("selected_channels", []))
    search_query = data.get("search_query", "")
    
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id != None)
        )
        all_assigned = {ch.telegram_id for ch in result.scalars().all()}
    
    scanned = await scan_user_channels()
    
    available = []
    for ch in scanned:
        if search_query and search_query.lower() not in ch.title.lower():
            continue
        
        is_selected = ch.id in selected
        
        if is_selected or ch.id not in all_assigned:
            available.append((ch.id, ch.title, is_selected))
    
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_channels_keyboard(available, cluster_id, page=page, search_query=search_query),
        )
    except TelegramBadRequest:
        pass
    
    await callback.answer()


@router.message(F.text == "🔍 Поиск", MenuStates.cluster_edit_channels)
async def msg_search_channels(message: Message, state: FSMContext) -> None:
    """Начало поиска каналов."""
    await state.set_state(InputStates.waiting_channel_search)
    await message.answer(
        "🔍 <b>Поиск каналов</b>\n\n"
        "Введите название канала или его часть:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(InputStates.waiting_channel_search)
async def process_search_query(message: Message, state: FSMContext) -> None:
    """Обработка поискового запроса."""
    if message.text == "❌ Отмена":
        await state.set_state(MenuStates.cluster_edit_channels)
        await message.answer(
            "Поиск отменён.",
            reply_markup=get_channels_save_keyboard(),
        )
        return
    
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    query = message.text.strip()
    selected = set(data.get("selected_channels", []))
    
    await state.update_data(search_query=query)
    await state.set_state(MenuStates.cluster_edit_channels)
    
    # Получаем каналы с фильтром
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id != None)
        )
        all_assigned = {ch.telegram_id for ch in result.scalars().all()}
    
    scanned = await scan_user_channels()
    
    # Фильтруем по поиску
    available = []
    for ch in scanned:
        if query.lower() not in ch.title.lower():
            continue
        
        is_selected = ch.id in selected
        if is_selected or ch.id not in all_assigned:
            available.append((ch.id, ch.title, is_selected))
    
    await message.answer(
        f"🔍 <b>Результаты поиска:</b> {query}\n\n"
        f"Найдено: {len(available)} каналов",
        reply_markup=get_channels_save_keyboard(),
    )
    await message.answer(
        "👇 <b>Каналы:</b>",
        reply_markup=get_channels_keyboard(available, cluster_id, page=0, search_query=query),
    )


@router.callback_query(F.data.startswith("ch_reset_search:"))
async def cb_reset_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Сброс поиска."""
    parts = callback.data.split(":")
    cluster_id = int(parts[1])
    
    data = await state.get_data()
    selected = set(data.get("selected_channels", []))
    
    await state.update_data(search_query="")
    
    # Перезагружаем список без фильтра
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id != None)
        )
        all_assigned = {ch.telegram_id for ch in result.scalars().all()}
    
    scanned = await scan_user_channels()
    
    available = []
    for ch in scanned:
        is_selected = ch.id in selected
        if is_selected or ch.id not in all_assigned:
            available.append((ch.id, ch.title, is_selected))
    
    await callback.message.edit_text(
        f"📢 <b>Выберите каналы:</b>\n\n"
        f"Доступно: {len(available)} каналов",
    )
    await callback.message.edit_reply_markup(
        reply_markup=get_channels_keyboard(available, cluster_id, page=0),
    )
    await callback.answer()


@router.message(F.text == "💾 Сохранить", MenuStates.cluster_edit_channels)
async def msg_channel_save(message: Message, state: FSMContext) -> None:
    """Сохранение выбранных каналов."""
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    selected = set(data.get("selected_channels", []))
    
    # Получаем информацию о каналах
    scanned = await scan_user_channels()
    channel_map = {ch.id: ch for ch in scanned}
    
    async with get_session() as session:
        # Получаем текущие каналы кластера
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster_id)
        )
        existing = {ch.telegram_id: ch for ch in result.scalars().all()}
        
        added = 0
        removed = 0
        
        # Добавляем новые
        for ch_id in selected:
            if ch_id not in existing and ch_id in channel_map:
                ch_info = channel_map[ch_id]
                channel = Channel(
                    telegram_id=ch_id,
                    title=ch_info.title,
                    username=ch_info.username,
                    cluster_id=cluster_id,
                )
                session.add(channel)
                added += 1
        
        # Удаляем убранные
        for ch_id, channel in existing.items():
            if ch_id not in selected:
                await session.delete(channel)
                removed += 1
        
        await session.commit()
    
    await state.set_state(MenuStates.cluster_view)
    
    await message.answer(
        f"✅ <b>Каналы сохранены!</b>\n\n"
        f"Добавлено: {added}\n"
        f"Удалено: {removed}",
        reply_markup=get_cluster_actions_keyboard(),
    )


@router.message(F.text == "❌ Отмена", MenuStates.cluster_edit_channels)
async def msg_channel_cancel(message: Message, state: FSMContext) -> None:
    """Отмена редактирования каналов."""
    await state.set_state(MenuStates.cluster_view)
    await message.answer(
        "❌ Редактирование отменено.",
        reply_markup=get_cluster_actions_keyboard(),
    )


# =============================================================================
# УПРАВЛЕНИЕ КАНАЛАМИ (УДАЛЕНИЕ)
# =============================================================================

@router.message(F.text == "📋 Управление каналами", MenuStates.cluster_view)
async def msg_manage_channels(message: Message, state: FSMContext) -> None:
    """Управление каналами в кластере (удаление)."""
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster_id)
        )
        channels = result.scalars().all()
    
    await state.set_state(MenuStates.cluster_manage_channels)
    
    if not channels:
        await message.answer(
            "📋 <b>Управление каналами</b>\n\n"
            "В этом кластере нет каналов.",
            reply_markup=get_back_keyboard_reply(),
        )
        return
    
    channels_data = [(ch.telegram_id, ch.title) for ch in channels]
    
    await message.answer(
        "📋 <b>Управление каналами</b>\n\n"
        "Нажмите на канал, чтобы удалить его из кластера:",
        reply_markup=get_back_keyboard_reply(),
    )
    await message.answer(
        "🗑 <b>Удалить канал:</b>",
        reply_markup=get_manage_channels_keyboard(channels_data, cluster_id),
    )


@router.callback_query(F.data.startswith("ch_remove:"))
async def cb_channel_remove(callback: CallbackQuery, state: FSMContext) -> None:
    """Удаление канала из кластера."""
    parts = callback.data.split(":")
    cluster_id = int(parts[1])
    channel_id = int(parts[2])
    
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(
                Channel.cluster_id == cluster_id,
                Channel.telegram_id == channel_id,
            )
        )
        channel = result.scalar_one_or_none()
        
        if channel:
            title = channel.title
            await session.delete(channel)
            await session.commit()
            
            await callback.answer(f"✅ Удалён: {title}", show_alert=True)
        else:
            await callback.answer("Канал не найден", show_alert=True)
            return
    
    # Обновляем список
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster_id)
        )
        channels = result.scalars().all()
    
    if not channels:
        await callback.message.edit_text(
            "📋 <b>Управление каналами</b>\n\n"
            "Все каналы удалены из кластера.",
        )
    else:
        channels_data = [(ch.telegram_id, ch.title) for ch in channels]
        await callback.message.edit_reply_markup(
            reply_markup=get_manage_channels_keyboard(channels_data, cluster_id),
        )


@router.message(F.text == "🔙 Назад", MenuStates.cluster_manage_channels)
async def msg_back_from_manage(message: Message, state: FSMContext) -> None:
    """Назад из управления каналами."""
    data = await state.get_data()
    cluster_id = data.get("cluster_id")
    
    async with get_session() as session:
        result = await session.execute(
            select(Cluster).where(Cluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        
        result = await session.execute(
            select(Channel).where(Channel.cluster_id == cluster_id)
        )
        channels = result.scalars().all()
    
    if cluster:
        channels_text = ""
        if channels:
            channels_text = "\n\n📢 <b>Каналы:</b>\n"
            for ch in channels[:10]:
                channels_text += f"• {ch.title}\n"
            if len(channels) > 10:
                channels_text += f"... и ещё {len(channels) - 10}"
        else:
            channels_text = "\n\n<i>Каналы не добавлены</i>"
        
        await state.set_state(MenuStates.cluster_view)
        await message.answer(
            f"📁 <b>Кластер: {cluster.name}</b>{channels_text}",
            reply_markup=get_cluster_actions_keyboard(),
        )


# =============================================================================
# СКАНИРОВАНИЕ КАНАЛОВ
# =============================================================================

@router.message(F.text.in_(["🔄 Сканировать каналы", "🔄 Сканировать\nканалы"]))
async def msg_scan_channels(message: Message, state: FSMContext) -> None:
    """Сканирование каналов пользователя."""
    await message.answer("🔄 <b>Сканирование каналов...</b>")
    
    try:
        channels = await scan_user_channels()
        
        await message.answer(
            f"✅ <b>Сканирование завершено!</b>\n\n"
            f"Найдено каналов и групп: <b>{len(channels)}</b>\n\n"
            "Теперь вы можете добавить их в кластеры.",
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка сканирования: {e}")
        await message.answer(
            f"❌ <b>Ошибка сканирования</b>\n\n"
            f"{str(e)[:200]}",
            reply_markup=get_main_menu_keyboard(),
        )


# =============================================================================
# ОБЩИЙ ОБРАБОТЧИК "НАЗАД"
# =============================================================================

@router.message(F.text == "🔙 Назад")
async def msg_back_general(message: Message, state: FSMContext) -> None:
    """Общий обработчик кнопки Назад."""
    current_state = await state.get_state()
    
    if current_state == MenuStates.clusters_list:
        await state.set_state(MenuStates.main_menu)
        await message.answer(
            "📱 <b>Главное меню</b>",
            reply_markup=get_main_menu_keyboard(),
        )
    elif current_state == MenuStates.cluster_view:
        await msg_clusters(message, state)
    elif current_state in (MenuStates.cluster_edit_channels, MenuStates.cluster_manage_channels):
        # Вернуться к просмотру кластера
        data = await state.get_data()
        cluster_id = data.get("cluster_id")
        
        if cluster_id:
            async with get_session() as session:
                result = await session.execute(
                    select(Cluster).where(Cluster.id == cluster_id)
                )
                cluster = result.scalar_one_or_none()
                
                result = await session.execute(
                    select(Channel).where(Channel.cluster_id == cluster_id)
                )
                channels = result.scalars().all()
            
            if cluster:
                channels_text = ""
                if channels:
                    channels_text = "\n\n📢 <b>Каналы:</b>\n"
                    for ch in channels[:10]:
                        channels_text += f"• {ch.title}\n"
                    if len(channels) > 10:
                        channels_text += f"... и ещё {len(channels) - 10}"
                else:
                    channels_text = "\n\n<i>Каналы не добавлены</i>"
                
                await state.set_state(MenuStates.cluster_view)
                await message.answer(
                    f"📁 <b>Кластер: {cluster.name}</b>{channels_text}",
                    reply_markup=get_cluster_actions_keyboard(),
                )
                return
        
        await msg_clusters(message, state)
    else:
        # По умолчанию — главное меню
        await state.set_state(MenuStates.main_menu)
        await message.answer(
            "📱 <b>Главное меню</b>",
            reply_markup=get_main_menu_keyboard(),
        )


# =============================================================================
# LEGACY CALLBACKS (для совместимости)
# =============================================================================

@router.callback_query(F.data == "clusters")
async def cb_clusters(callback: CallbackQuery, state: FSMContext) -> None:
    """Legacy callback для кластеров."""
    await callback.message.answer(
        "Используйте кнопки внизу экрана 👇",
        reply_markup=get_clusters_menu_keyboard(),
    )
    await state.set_state(MenuStates.clusters_list)
    await callback.answer()


@router.callback_query(F.data == "scan_channels")
async def cb_scan_channels(callback: CallbackQuery, state: FSMContext) -> None:
    """Legacy callback для сканирования."""
    await callback.message.answer("🔄 <b>Сканирование каналов...</b>")
    await callback.answer()
    
    try:
        channels = await scan_user_channels()
        
        await callback.message.answer(
            f"✅ <b>Сканирование завершено!</b>\n\n"
            f"Найдено каналов и групп: <b>{len(channels)}</b>\n\n"
            "Теперь вы можете добавить их в кластеры.",
            reply_markup=get_main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка сканирования: {e}")
        await callback.message.answer(
            f"❌ <b>Ошибка сканирования</b>\n\n"
            f"{str(e)[:200]}",
            reply_markup=get_main_menu_keyboard(),
        )

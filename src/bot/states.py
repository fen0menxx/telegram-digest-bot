"""
FSM-состояния для бота.

Отслеживание текущего "экрана" пользователя.
"""

from aiogram.fsm.state import State, StatesGroup


class MenuStates(StatesGroup):
    """Состояния навигации по меню."""
    main_menu = State()
    clusters_list = State()
    cluster_view = State()
    cluster_edit_channels = State()
    cluster_manage_channels = State()
    digest_select_cluster = State()
    digest_select_period = State()
    settings_menu = State()


class InputStates(StatesGroup):
    """Состояния ввода данных."""
    waiting_cluster_name = State()
    waiting_cluster_rename = State()
    waiting_channel_search = State()
    waiting_channel_link = State()
    waiting_confirm_delete = State()


# Данные в state.data:
# - cluster_id: int — текущий выбранный кластер
# - selected_channels: set[int] — выбранные каналы при редактировании
# - search_query: str — поисковый запрос каналов
# - digest_cluster_id: int | "all" — кластер для дайджеста































from aiogram.fsm.state import State, StatesGroup


class AuthState(StatesGroup):
    waiting_for_steam_name = State()
    waiting_for_steam_password = State()
    waiting_for_language = State()
    waiting_for_guard_code = State()


class DungeonState(StatesGroup):
    dungeon_id = State()


class AdminState(StatesGroup):
    broadcast_message = State()

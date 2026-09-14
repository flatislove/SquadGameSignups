from aiogram.fsm.state import State, StatesGroup

class NewGameForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_end_time = State()
    waiting_for_loc_name = State()
    waiting_for_loc_link = State()
    waiting_for_cost = State()
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_max_players = State()
    waiting_for_pub_time = State()
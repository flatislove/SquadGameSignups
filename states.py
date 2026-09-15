from aiogram.fsm.state import State, StatesGroup

class NewGameForm(StatesGroup):
    date = State()
    time = State()
    end_time = State()
    loc_name = State()
    loc_link = State()
    cost = State()
    phone = State()
    name = State()
    max_players = State()
    pub_time = State()
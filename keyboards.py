from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Создать игру", callback_data="menu_new_game")
    builder.button(text="💳 Управление оплатой", callback_data="menu_payments")
    builder.adjust(1)
    return builder.as_markup()

def get_match_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Записаться", callback_data="signup")
    builder.adjust(1)
    return builder.as_markup()

def get_groups_keyboard(admin_groups, action_prefix: str):
    builder = InlineKeyboardBuilder()
    for chat_id, title in admin_groups:
        builder.button(text=title, callback_data=f"{action_prefix}_{chat_id}")
    builder.button(text="« Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    return builder.as_markup()

def get_players_pay_keyboard(players, chat_id: str):
    builder = InlineKeyboardBuilder()
    for uid, pdata in players.items():
        paid_mark = "🟩" if pdata.get("paid", False) else "🟧"
        builder.button(text=f"{paid_mark} {pdata['name']}", callback_data=f"pm_pay_{chat_id}_{uid}")
    builder.button(text="« Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    return builder.as_markup()
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://flatislove.github.io/SquadGameSignups/")

def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Создать игру", callback_data="menu_new_game")
    builder.button(text="💳 Управление оплатой", callback_data="menu_payments")
    builder.button(text="📢 Управление анонсами", callback_data="menu_manage_announcements")
    builder.adjust(1)
    return builder.as_markup()

def get_match_keyboard(chat_id: str):
    builder = InlineKeyboardBuilder()
    app_url = f"{WEB_APP_URL.rstrip('/')}/?chat_id={chat_id}"
    builder.button(text="📋 Открыть запись", web_app=types.WebAppInfo(url=app_url))
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

def get_scheduled_announcements_keyboard(jobs_list):
    builder = InlineKeyboardBuilder()
    for job in jobs_list:
        chat_id = job.id.replace("pub_match_", "")
        run_time = job.next_run_time.strftime("%d.%m.%Y %H:%M") if job.next_run_time else "скрыто"
        builder.button(text=f"🛑 Остановить анонс ({run_time})", callback_data=f"stop_announcement_{chat_id}")
    builder.button(text="« Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    return builder.as_markup()
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from storage import load_data, save_data
from keyboards import get_main_menu_keyboard

router = Router()

@router.my_chat_member()
async def bot_added_to_chat(event: types.ChatMemberUpdated):
    if event.chat.type in ["group", "supergroup"]:
        if event.new_chat_member.status in ["member", "administrator"]:
            chat_id = str(event.chat.id)
            data = load_data()
            groups = data.setdefault("groups", {})
            if chat_id not in groups:
                groups[chat_id] = {}
            groups[chat_id]["group_title"] = event.chat.title
            save_data(data)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        chat_id = str(message.chat.id)
        data = load_data()
        groups = data.setdefault("groups", {})
        if chat_id not in groups:
            groups[chat_id] = {}
        groups[chat_id]["group_title"] = message.chat.title
        save_data(data)
    else:
        await message.answer(
            "Привет! Я бот для организации волейбольных матчей.\nВыберите действие:",
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(lambda c: c.data == "menu_main")
async def menu_main_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню управления матчами:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()
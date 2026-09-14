from aiogram import Router, types

from loader import bot
from storage import get_chat_data
from keyboards import get_main_menu_keyboard, get_groups_keyboard, get_players_pay_keyboard
from utils import get_user_admin_groups, update_group_announcement

router = Router()

async def show_group_players_for_pay(callback_or_message, chat_id: str, is_callback: bool = True):
    chat_data = get_chat_data(chat_id)
    if not chat_data.get("active_match"):
        text = "В этой группе сейчас нет активного матча."
        if is_callback:
            await callback_or_message.message.edit_text(text, reply_markup=get_main_menu_keyboard())
        else:
            await callback_or_message.answer(text, reply_markup=get_main_menu_keyboard())
        return

    players = chat_data.get("players", {})
    if not players:
        text = "Основной список участников в этой группе пуст."
        if is_callback:
            await callback_or_message.message.edit_text(text, reply_markup=get_main_menu_keyboard())
        else:
            await callback_or_message.answer(text, reply_markup=get_main_menu_keyboard())
        return

    text = f"Управление оплатой для группы *{chat_data.get('group_title', chat_id)}*:"
    markup = get_players_pay_keyboard(players, chat_id)
    
    if is_callback:
        await callback_or_message.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await callback_or_message.answer(text, parse_mode="Markdown", reply_markup=markup)

@router.callback_query(lambda c: c.data == "menu_payments")
async def menu_payments_callback(callback: types.CallbackQuery):
    admin_groups = await get_user_admin_groups(bot, callback.from_user.id)
    if not admin_groups:
        await callback.answer("Вы не являетесь администратором ни в одной из подключенных групп.", show_alert=True)
        return

    if len(admin_groups) == 1:
        await show_group_players_for_pay(callback, admin_groups[0][0], is_callback=True)
    else:
        await callback.message.edit_text(
            "Выберите группу для управления оплатой:",
            reply_markup=get_groups_keyboard(admin_groups, "sel_pay_group")
        )
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("sel_pay_group_"))
async def process_select_pay_group(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[3]
    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=callback.from_user.id)
        if member.status not in ["creator", "administrator"]:
            await callback.answer("У вас нет прав администратора в этой группе.", show_alert=True)
            return
    except Exception:
        await callback.answer("Ошибка проверки прав.", show_alert=True)
        return

    await show_group_players_for_pay(callback, chat_id, is_callback=True)

@router.callback_query(lambda c: c.data and c.data.startswith("pm_pay_"))
async def process_pm_pay_selection(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    chat_id = parts[2]
    target_uid = parts[3]

    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=callback.from_user.id)
        if member.status not in ["creator", "administrator"]:
            await callback.answer("Только администраторы могут изменять статус оплаты!", show_alert=True)
            return
    except Exception:
        await callback.answer("Ошибка проверки прав.", show_alert=True)
        return

    chat_data = get_chat_data(chat_id)
    players = chat_data.get("players", {})
    
    if target_uid in players:
        current_status = players[target_uid].get("paid", False)
        players[target_uid]["paid"] = not current_status
        get_chat_data(chat_id) 
        from storage import update_chat_data
        update_chat_data(chat_id, chat_data)

        await update_group_announcement(bot, chat_id)

        players_sub = chat_data.get("players", {})
        markup = get_players_pay_keyboard(players_sub, chat_id)

        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass
            
    await callback.answer("Статус обновлен")
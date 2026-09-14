from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from loader import bot
from storage import get_chat_data, update_chat_data
from keyboards import get_match_keyboard
from utils import escape_md, build_announcement_text, update_group_announcement

router = Router()

async def notify_admins_action(chat_id: str, action_text: str, user: types.User):
    group_data = get_chat_data(chat_id)
    group_title = group_data.get("group_title", f"Группа {chat_id}")
    
    username_str = f"@{user.username}" if user.username else "нет юзернейма"
    msg = (
        f"📢 *Log Event*\n"
        f"Группа: *{escape_md(group_title)}*\n"
        f"Действие: *{escape_md(action_text)}*\n\n"
        f"👤 Имя: *{escape_md(user.full_name)}*\n"
        f"🔗 Юзернейм: {username_str}\n"
        f"🆔 Telegram ID: `{user.id}`"
    )

    try:
        chat_admins = await bot.get_chat_administrators(int(chat_id))
        for admin in chat_admins:
            if admin.user.is_bot:
                continue
            try:
                await bot.send_message(
                    chat_id=admin.user.id,
                    text=msg,
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    except Exception as e:
        print(f"Failed to fetch chat admins for logging: {e}")

@router.callback_query(lambda c: c.data == "signup")
async def process_signup(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    user = callback.from_user
    user_id = str(user.id)
    full_name = user.full_name
    
    chat_data = get_chat_data(chat_id)
    if not chat_data.get("active_match"):
        await callback.answer("В данный момент нет активного матча!", show_alert=True)
        return
    
    players = chat_data.setdefault("players", {})
    reserve = chat_data.setdefault("reserve", {})
    refund_pending = chat_data.setdefault("refund_pending", {})
    paid_spot_transfers = chat_data.setdefault("paid_spot_transfers", {})
    
    max_players = int(chat_data.get("match_details", {}).get("max_players", 12))
    
    if user_id in players:
        pdata = players[user_id]
        if pdata.get("paid", False):
            if reserve:
                next_reserve_uid, next_reserve_data = next(iter(reserve.items()))
                
                paid_spot_transfers[user_id] = {
                    "leaving_user_name": full_name,
                    "receiver_uid": next_reserve_uid,
                    "receiver_name": next_reserve_data["name"],
                    "pdata": pdata
                }
                
                del players[user_id]
                del reserve[next_reserve_uid]
                
                update_chat_data(chat_id, chat_data)
                await update_group_announcement(bot, chat_id)
                
                try:
                    kb = InlineKeyboardBuilder()
                    kb.button(text="✅ Да, деньги переведены", callback_data=f"transfer_yes_{chat_id}_{user_id}_{next_reserve_uid}")
                    kb.button(text="❌ Нет", callback_data=f"transfer_no_{chat_id}_{user_id}_{next_reserve_uid}")
                    kb.adjust(1)
                    
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=f"🔄 Игрок *{escape_md(next_reserve_data['name'])}* из резерва занял ваше место в группе *{escape_md(chat_data.get('group_title'))}*.\n\nПеревел ли он вам деньги за вашу оплату (`🟩`)?",
                        parse_mode="Markdown",
                        reply_markup=kb.as_markup()
                    )
                except Exception as e:
                    print(f"Failed to send transfer request to user: {e}")
                
                status_text = "Вы выписаны. Бот уточняет у вас в ЛС насчет перевода денег."
                await notify_admins_action(chat_id, "Отмена записи (оплачено, передача места резервисту)", user)
            else:
                refund_pending[user_id] = pdata
                del players[user_id]
                update_chat_data(chat_id, chat_data)
                
                group_title = chat_data.get("group_title", f"Группа {chat_id}")
                try:
                    chat_admins = await bot.get_chat_administrators(int(chat_id))
                    for admin in chat_admins:
                        if admin.user.is_bot:
                            continue
                        kb = InlineKeyboardBuilder()
                        kb.button(text="✅ Подтвердить возврат", callback_data=f"refund_ok_{chat_id}_{user_id}")
                        kb.adjust(1)
                        
                        await bot.send_message(
                            chat_id=admin.user.id,
                            text=f"⚠️ *Внимание!* Игрок *{escape_md(full_name)}* отменил запись в группе *{escape_md(group_title)}*, но у него стояла отметка об оплате 🟩.\nНеобходимо вернуть деньги!",
                            parse_mode="Markdown",
                            reply_markup=kb.as_markup()
                        )
                except Exception as e:
                    print(f"Failed to notify admins about refund: {e}")

                status_text = "Вы выписаны. Администратор уведомлен о возврате оплаты."
                await notify_admins_action(chat_id, "Отмена записи (оплачено, требуется возврат средств)", user)
        else:
            del players[user_id]
            if reserve:
                r_uid, r_data = next(iter(reserve.items()))
                del reserve[r_uid]
                players[r_uid] = {"name": r_data["name"], "paid": False}
            update_chat_data(chat_id, chat_data)
            status_text = "Вы выписаны из списка участников."
            await notify_admins_action(chat_id, "Отмена записи из основного состава", user)

    elif user_id in reserve:
        del reserve[user_id]
        update_chat_data(chat_id, chat_data)
        status_text = "Вы удалены из резерва."
        await notify_admins_action(chat_id, "Отмена записи из резерва", user)

    else:
        if len(players) < max_players:
            was_paid = False
            if user_id in refund_pending:
                was_paid = True
                del refund_pending[user_id]
                
            players[user_id] = {"name": full_name, "paid": was_paid}
            status_text = "Вы успешно записались в основной состав!"
            await notify_admins_action(chat_id, "Запись в основной состав", user)
        else:
            reserve[user_id] = {"name": full_name}
            status_text = "Мест нет, вы добавлены в Резерв!"
            await notify_admins_action(chat_id, "Запись в резерв", user)
        update_chat_data(chat_id, chat_data)
    
    try:
        await callback.message.edit_text(
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=get_match_keyboard()
        )
    except Exception as e:
        print(f"Failed to update message on signup: {e}")
        
    await callback.answer(status_text)

@router.callback_query(lambda c: c.data and (c.data.startswith("transfer_yes_") or c.data.startswith("transfer_no_")))
async def process_transfer_confirmation(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]
    chat_id = parts[2]
    leaving_uid = parts[3]
    receiver_uid = parts[4]

    chat_data = get_chat_data(chat_id)
    players = chat_data.setdefault("players", {})
    reserve = chat_data.setdefault("reserve", {})
    refund_pending = chat_data.setdefault("refund_pending", {})
    paid_spot_transfers = chat_data.setdefault("paid_spot_transfers", {})

    transfer_info = paid_spot_transfers.get(leaving_uid)
    if not transfer_info:
        await callback.message.edit_text("ℹ️ Информация об этом переводе уже устарела или обработана.")
        await callback.answer()
        return

    receiver_name = transfer_info["receiver_name"]
    pdata = transfer_info["pdata"]

    if action == "yes":
        players[receiver_uid] = {"name": receiver_name, "paid": True}
        del paid_spot_transfers[leaving_uid]
        update_chat_data(chat_id, chat_data)
        await update_group_announcement(bot, chat_id)
        
        await callback.message.edit_text(f"✅ Спасибо! Место передано игроку *{escape_md(receiver_name)}* со статусом оплаты (🟩).", parse_mode="Markdown")
        await notify_admins_action(chat_id, f"Подтвержден перевод денег за место от резервиста ({transfer_info['leaving_user_name']} -> {receiver_name})", callback.from_user)
    else:
        del paid_spot_transfers[leaving_uid]
        refund_pending[leaving_uid] = pdata
        
        new_reserve = {receiver_uid: {"name": receiver_name}}
        new_reserve.update(reserve)
        chat_data["reserve"] = new_reserve
        update_chat_data(chat_id, chat_data)
        await update_group_announcement(bot, chat_id)

        group_title = chat_data.get("group_title", f"Группа {chat_id}")
        try:
            chat_admins = await bot.get_chat_administrators(int(chat_id))
            for admin in chat_admins:
                if admin.user.is_bot:
                    continue
                kb = InlineKeyboardBuilder()
                kb.button(text="✅ Подтвердить возврат", callback_data=f"refund_ok_{chat_id}_{leaving_uid}")
                kb.adjust(1)
                
                await bot.send_message(
                    chat_id=admin.user.id,
                    text=f"⚠️ *Внимание!* Игрок отменил запись и сообщил, что перевод от резервиста *не* поступил. Требуется вернуть деньги игроку *{escape_md(transfer_info['leaving_user_name'])}* в группе *{escape_md(group_title)}*!",
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
        except Exception as e:
            print(f"Failed to notify admins about failed transfer refund: {e}")

        await callback.message.edit_text("❌ Вы указали, что перевод не поступил. Администратор уведомлен о необходимости возврата.")
        await notify_admins_action(chat_id, "Отказ от перевода средств резервистом (требуется возврат средств)", callback.from_user)

    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("refund_ok_"))
async def process_refund_confirmation(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    chat_id = parts[2]
    target_uid = parts[3]

    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=callback.from_user.id)
        if member.status not in ["creator", "administrator"]:
            await callback.answer("Только администраторы могут подтверждать возврат!", show_alert=True)
            return
    except Exception:
        await callback.answer("Ошибка проверки прав.", show_alert=True)
        return

    chat_data = get_chat_data(chat_id)
    refund_pending = chat_data.setdefault("refund_pending", {})
    
    if target_uid in refund_pending:
        del refund_pending[target_uid]
        update_chat_data(chat_id, chat_data)
        await callback.message.edit_text(f"✅ Возврат для игрока подтвержден. Статус сброшен.")
        await notify_admins_action(chat_id, f"Администратором подтвержден возврат денег игроку (ID: {target_uid})", callback.from_user)
    else:
        await callback.message.edit_text(f"ℹ️ Возврат по этому игроку уже был обработан ранее.")
        
    await callback.answer("Возврат подтвержден")
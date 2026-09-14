from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states import NewGameForm
from keyboards import (
    get_main_menu_keyboard,
    get_match_keyboard,
    get_groups_keyboard,
    get_players_pay_keyboard
)
from storage import load_data, save_data, get_chat_data, update_chat_data

LOCAL_TZ = timezone(timedelta(hours=5))

def escape_md(text: str) -> str:
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text

def build_announcement_text(chat_data: dict):
    details = chat_data.get("match_details", {
        "date": "TBD", "time": "TBD", "end_time": "TBD",
        "loc_name": "TBD", "loc_link": "", "cost": "0",
        "phone": "TBD", "name": "TBD", "max_players": 12
    })
    
    max_p = int(details.get("max_players", 12))
    players = chat_data.get("players", {})
    reserve = chat_data.get("reserve", {})
    
    players_lines = []
    player_items = list(players.items())
    for i, (uid, pdata) in enumerate(player_items):
        full_name = pdata["name"]
        safe_name = escape_md(full_name)
        user_link = f"[{safe_name}](tg://user?id={uid})"
        paid_mark = "🟩" if pdata.get("paid", False) else "🟧"
        players_lines.append(f"{paid_mark} {i+1}. {user_link}")
        
    players_list_text = "\n".join(players_lines) if players_lines else "_Пока нет участников._"
        
    reserve_lines = []
    reserve_items = list(reserve.items())
    for i, (uid, rdata) in enumerate(reserve_items):
        full_name = rdata["name"]
        safe_name = escape_md(full_name)
        user_link = f"[{safe_name}](tg://user?id={uid})"
        reserve_lines.append(f"🟦 {i+1}. {user_link}")
        
    reserve_section = ""
    if reserve_lines:
        reserve_section = f"\n\n*Резерв ({len(reserve)}):*\n" + "\n".join(reserve_lines)

    loc_display = f"[{details['loc_name']}]({details['loc_link']})" if details.get('loc_link') else details['loc_name']
    time_display = f"{details['time']} - {details['end_time']}" if details.get('end_time') else details['time']
    
    total_count = len(players)
    
    return (
        f"🏐 *Волейбол* (Основной состав: {total_count}/{max_p})\n\n"
        f"📅 *Дата:* {details['date']}\n"
        f"⏰ *Время:* {time_display}\n"
        f"📍 *Место:* {loc_display}\n"
        f"💰 *Стоимость:* {details['cost']} KZT\n"
        f"💳 {details['phone']} ({details['name']})\n\n"
        f"*Участники:*\n{players_list_text}"
        f"{reserve_section}"
    )

async def update_group_announcement(bot: Bot, chat_id: str):
    chat_data = get_chat_data(chat_id)
    msg_id = chat_data.get("announcement_message_id")
    if not msg_id:
        return
    try:
        await bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(msg_id),
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=get_match_keyboard()
        )
    except Exception as e:
        print(f"Failed to update group announcement: {e}")

async def get_user_admin_groups(bot: Bot, user_id: int):
    data = load_data()
    groups = data.get("groups", {})
    admin_groups = []
    for chat_id, chat_data in groups.items():
        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user_id)
            if member.status in ["creator", "administrator"]:
                title = chat_data.get("group_title", f"Группа {chat_id}")
                admin_groups.append((chat_id, title))
        except Exception:
            continue
    return admin_groups

def register_handlers(dp: Dispatcher, bot: Bot, scheduler: AsyncIOScheduler):

    @dp.my_chat_member()
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

    @dp.message(Command("start"))
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

    @dp.callback_query(lambda c: c.data == "menu_main")
    async def menu_main_callback(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(
            "Главное меню управления матчами:",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "menu_new_game")
    async def menu_new_game_callback(callback: types.CallbackQuery, state: FSMContext):
        admin_groups = await get_user_admin_groups(bot, callback.from_user.id)
        if not admin_groups:
            await callback.answer("Сначала добавьте бота в группу и получите права администратора.", show_alert=True)
            return

        if len(admin_groups) == 1:
            await state.update_data(target_chat_id=admin_groups[0][0], group_title=admin_groups[0][1])
            await state.set_state(NewGameForm.waiting_for_date)
            await callback.message.edit_text(f"Создание матча для группы: *{admin_groups[0][1]}*\n\n📅 Введите дату матча (например, 20.09.2026):", parse_mode="Markdown")
        else:
            await callback.message.edit_text(
                "Выберите группу, для которой хотите создать матч:",
                reply_markup=get_groups_keyboard(admin_groups, "sel_new_group")
            )
        await callback.answer()

    @dp.callback_query(lambda c: c.data and c.data.startswith("sel_new_group_"))
    async def process_select_new_group(callback: types.CallbackQuery, state: FSMContext):
        chat_id = callback.data.split("_")[3]
        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=callback.from_user.id)
            if member.status not in ["creator", "administrator"]:
                await callback.answer("У вас нет прав администратора в этой группе.", show_alert=True)
                return
        except Exception:
            await callback.answer("Ошибка проверки прав.", show_alert=True)
            return

        data = load_data()
        group_title = data.get("groups", {}).get(chat_id, {}).get("group_title", f"Группа {chat_id}")

        await state.update_data(target_chat_id=chat_id, group_title=group_title)
        await state.set_state(NewGameForm.waiting_for_date)
        await callback.message.edit_text(f"Создание матча для группы: *{group_title}*\n\n📅 Введите дату матча (например, 20.09.2026):", parse_mode="Markdown")
        await callback.answer()

    @dp.message(NewGameForm.waiting_for_date)
    async def process_match_date(message: types.Message, state: FSMContext):
        await state.update_data(date=message.text)
        await state.set_state(NewGameForm.waiting_for_time)
        await message.answer("⏰ Введите время начала матча (например, 19:00):")

    @dp.message(NewGameForm.waiting_for_time)
    async def process_match_time(message: types.Message, state: FSMContext):
        await state.update_data(time=message.text)
        await state.set_state(NewGameForm.waiting_for_end_time)
        await message.answer("🏁 Введите время окончания матча (например, 21:00):")

    @dp.message(NewGameForm.waiting_for_end_time)
    async def process_match_end_time(message: types.Message, state: FSMContext):
        await state.update_data(end_time=message.text)
        await state.set_state(NewGameForm.waiting_for_loc_name)
        await message.answer("📍 Введите название места (например, Спортивный зал №1):")

    @dp.message(NewGameForm.waiting_for_loc_name)
    async def process_match_loc_name(message: types.Message, state: FSMContext):
        await state.update_data(loc_name=message.text)
        await state.set_state(NewGameForm.waiting_for_loc_link)
        await message.answer("🔗 Введите ссылку на карту (например, https://maps.app.goo.gl/...):")

    @dp.message(NewGameForm.waiting_for_loc_link)
    async def process_match_loc_link(message: types.Message, state: FSMContext):
        await state.update_data(loc_link=message.text)
        await state.set_state(NewGameForm.waiting_for_cost)
        await message.answer("💰 Введите стоимость в KZT (например, 2500):")

    @dp.message(NewGameForm.waiting_for_cost)
    async def process_match_cost(message: types.Message, state: FSMContext):
        await state.update_data(cost=message.text)
        await state.set_state(NewGameForm.waiting_for_phone)
        await message.answer("📱 Введите номер телефона для перевода (например, +77011234567):")

    @dp.message(NewGameForm.waiting_for_phone)
    async def process_match_phone(message: types.Message, state: FSMContext):
        await state.update_data(phone=message.text)
        await state.set_state(NewGameForm.waiting_for_name)
        await message.answer("👤 Введите имя получателя (например, Владислав В.):")

    @dp.message(NewGameForm.waiting_for_name)
    async def process_match_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await state.set_state(NewGameForm.waiting_for_max_players)
        await message.answer("👥 Введите максимальное количество игроков в основном составе (например, 12):")

    @dp.message(NewGameForm.waiting_for_max_players)
    async def process_match_max_players(message: types.Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer("Пожалуйста, введите число (например, 12):")
            return
        await state.update_data(max_players=int(message.text))
        await state.set_state(NewGameForm.waiting_for_pub_time)
        await message.answer("🚀 Введите время публикации анонса (формат: ДД.ММ.ГГГГ ЧЧ:ММ, например, 18.09.2026 12:00):")

    @dp.message(NewGameForm.waiting_for_pub_time)
    async def process_pub_time(message: types.Message, state: FSMContext):
        pub_time_str = message.text
        form_data = await state.get_data()
        await state.clear()

        try:
            pub_dt_local = datetime.strptime(pub_time_str.strip(), "%d.%m.%Y %H:%M")
            pub_dt_local = pub_dt_local.replace(tzinfo=LOCAL_TZ)
            pub_dt_utc = pub_dt_local.astimezone(timezone.utc)
        except ValueError:
            await message.answer("Неверный формат даты! Используйте ДД.ММ.ГГГГ ЧЧ:ММ. Нажмите «Создать игру» в меню снова.")
            return

        chat_id = form_data["target_chat_id"]
        data = load_data()
        groups = data.setdefault("groups", {})
        chat_data = groups.setdefault(chat_id, {})
        
        chat_data["group_title"] = form_data["group_title"]
        chat_data["match_details"] = {
            "date": form_data["date"], "time": form_data["time"],
            "end_time": form_data["end_time"], "loc_name": form_data["loc_name"],
            "loc_link": form_data["loc_link"], "cost": form_data["cost"],
            "phone": form_data["phone"], "name": form_data["name"],
            "max_players": form_data["max_players"]
        }
        save_data(data)

        job_id = f"pub_match_{chat_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            send_custom_announcement,
            "date",
            run_date=pub_dt_utc,
            args=[bot, chat_id],
            id=job_id,
            replace_existing=True
        )

        await message.answer(
            f"Матч успешно запланирован к публикации на {pub_time_str} для группы *{form_data['group_title']}*!",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    async def send_custom_announcement(bot_instance: Bot, chat_id: str):
        chat_data = get_chat_data(chat_id)
        chat_data["active_match"] = True
        chat_data["players"] = {}
        chat_data["reserve"] = {}
        chat_data["refund_pending"] = {}
        chat_data["paid_spot_transfers"] = {}
        update_chat_data(chat_id, chat_data)
        
        try:
            sent_msg = await bot_instance.send_message(
                chat_id=int(chat_id),
                text=build_announcement_text(chat_data),
                parse_mode="Markdown",
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                reply_markup=get_match_keyboard()
            )
            chat_data["announcement_message_id"] = str(sent_msg.message_id)
            update_chat_data(chat_id, chat_data)
        except Exception as e:
            print(f"Failed to send scheduled announcement to {chat_id}: {e}")

    @dp.callback_query(lambda c: c.data == "menu_payments")
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

    @dp.callback_query(lambda c: c.data and c.data.startswith("sel_pay_group_"))
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

    @dp.callback_query(lambda c: c.data and c.data.startswith("pm_pay_"))
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
            update_chat_data(chat_id, chat_data)

            await update_group_announcement(bot, chat_id)

            players_sub = chat_data.get("players", {})
            markup = get_players_pay_keyboard(players_sub, chat_id)

            try:
                await callback.message.edit_reply_markup(reply_markup=markup)
            except Exception:
                pass
                
        await callback.answer("Статус обновлен")

    @dp.callback_query(lambda c: c.data == "signup")
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
            else:
                del players[user_id]
                if reserve:
                    r_uid, r_data = next(iter(reserve.items()))
                    del reserve[r_uid]
                    players[r_uid] = {"name": r_data["name"], "paid": False}
                update_chat_data(chat_id, chat_data)
                status_text = "Вы выписаны из списка участников."

        elif user_id in reserve:
            del reserve[user_id]
            update_chat_data(chat_id, chat_data)
            status_text = "Вы удалены из резерва."

        else:
            if len(players) < max_players:
                was_paid = False
                if user_id in refund_pending:
                    was_paid = True
                    del refund_pending[user_id]
                players[user_id] = {"name": full_name, "paid": was_paid}
                status_text = "Вы успешно записались в основной состав!"
            else:
                reserve[user_id] = {"name": full_name}
                status_text = "Мест нет, вы добавлены в Резерв!"
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

    @dp.callback_query(lambda c: c.data and (c.data.startswith("transfer_yes_") or c.data.startswith("transfer_no_")))
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

        await callback.answer()

    @dp.callback_query(lambda c: c.data and c.data.startswith("refund_ok_"))
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
        else:
            await callback.message.edit_text(f"ℹ️ Возврат по этому игроку уже был обработан ранее.")
            
        await callback.answer("Возврат подтвержден")
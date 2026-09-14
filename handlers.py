from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
        "phone": "TBD", "name": "TBD"
    })
    
    players = chat_data.get("players", {})
    if players:
        players_lines = []
        for i, (uid, pdata) in enumerate(players.items()):
            full_name = pdata["name"]
            safe_name = escape_md(full_name)
            user_link = f"[{safe_name}](tg://user?id={uid})"
            paid_mark = "🟩" if pdata.get("paid", False) else "🟧"
            players_lines.append(f"{i+1}. {user_link} — {paid_mark}")
        players_list_text = "\n".join(players_lines)
    else:
        players_list_text = "_Пока нет участников._"
        
    loc_display = f"[{details['loc_name']}]({details['loc_link']})" if details.get('loc_link') else details['loc_name']
    time_display = f"{details['time']} - {details['end_time']}" if details.get('end_time') else details['time']
    
    return (
        f"🏐 *Волейбол*\n\n"
        f"📅 *Дата:* {details['date']}\n"
        f"⏰ *Время:* {time_display}\n"
        f"📍 *Место:* {loc_display}\n"
        f"💰 *Стоимость:* {details['cost']} KZT\n"
        f"💳 *Перевод:* {details['phone']} ({details['name']})\n\n"
        f"*Участники ({len(players)}):*\n{players_list_text}"
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
            "phone": form_data["phone"], "name": form_data["name"]
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
            text = "Список участников в этой группе пуст."
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
        
        if user_id in players:
            del players[user_id]
            status_text = "Вы выписаны из списка участников."
        else:
            players[user_id] = {"name": full_name, "paid": False}
            status_text = "Вы успешно записались!"
            
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
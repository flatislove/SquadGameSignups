import logging
from datetime import datetime, timezone
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from loader import bot, scheduler
from states import NewGameForm
from storage import load_data, save_data, get_chat_data, update_chat_data
from keyboards import (
    get_main_menu_keyboard, 
    get_groups_keyboard, 
    get_match_keyboard, 
    get_scheduled_announcements_keyboard
)
from utils import LOCAL_TZ, build_announcement_text, get_user_admin_groups, escape_md, update_group_announcement

router = Router()

FORM_STEPS = [
    (NewGameForm.waiting_for_date, "📅 Введите дату матча (например, 20.09.2026):"),
    (NewGameForm.waiting_for_time, "⏰ Введите время начала матча (например, 19:00):"),
    (NewGameForm.waiting_for_end_time, "🏁 Введите время окончания матча (например, 21:00):"),
    (NewGameForm.waiting_for_loc_name, "📍 Введите название места (например, Спортивный зал №1):"),
    (NewGameForm.waiting_for_loc_link, "🔗 Введите ссылку на карту (например, https://maps.app.goo.gl/...):"),
    (NewGameForm.waiting_for_cost, "💰 Введите стоимость в KZT (например, 2500):"),
    (NewGameForm.waiting_for_phone, "📱 Введите номер телефона для перевода (например, +77011234567):"),
    (NewGameForm.waiting_for_name, "👤 Введите имя получателя (например, Владислав В.):"),
    (NewGameForm.waiting_for_max_players, "👥 Введите максимальное количество игроков в основном составе (например, 12):"),
    (NewGameForm.waiting_for_pub_time, "🚀 Введите время публикации анонса (формат: ДД.ММ.ГГГГ ЧЧ:ММ, например, 18.09.2026 12:00):")
]

FORM_KEYS = ["date", "time", "end_time", "loc_name", "loc_link", "cost", "phone", "name", "max_players", "pub_time"]
FORM_LABELS = ["Дата", "Начало", "Конец", "Место", "Ссылка", "Цена", "Телефон", "Получатель", "Максимум", "Публикация"]

async def show_step(message_or_callback, state: FSMContext, step_idx: int, edit: bool = True):
    await state.update_data(current_step=step_idx)
    state_to_set, prompt_text = FORM_STEPS[step_idx]
    await state.set_state(state_to_set)

    data = await state.get_data()
    group_title = data.get("group_title", "Группа")

    filled_info = f"🛠 Создание матча для: *{escape_md(group_title)}*\n\n"
    
    for i in range(step_idx):
        val = data.get(FORM_KEYS[i])
        if val:
            filled_info += f"▫️ {FORM_LABELS[i]}: {escape_md(str(val))}\n"

    filled_info += f"\n*{prompt_text}*"

    kb = InlineKeyboardBuilder()
    if step_idx > 0:
        kb.button(text="⬅️ Назад", callback_data="form_back")
    if step_idx < len(FORM_STEPS) - 1:
        kb.button(text="Вперед ➡️", callback_data="form_forward")
    kb.button(text="❌ Отменить", callback_data="form_cancel")
    kb.adjust(2, 1)

    if edit and isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(filled_info, parse_mode="Markdown", reply_markup=kb.as_markup())
        except Exception:
            pass
    elif isinstance(message_or_callback, types.Message):
        try:
            await message_or_callback.delete()
        except Exception:
            pass
        data_msg_id = data.get("form_message_id")
        chat_id = message_or_callback.chat.id
        if data_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=int(data_msg_id),
                    text=filled_info, parse_mode="Markdown", reply_markup=kb.as_markup()
                )
                return
            except Exception:
                pass
        sent = await message_or_callback.answer(filled_info, parse_mode="Markdown", reply_markup=kb.as_markup())
        await state.update_data(form_message_id=sent.message_id)

async def send_custom_announcement(chat_id: str):
    logging.info(f"[Scheduler] Сработала задача отправки анонса для чата {chat_id}")
    chat_data = get_chat_data(chat_id)
    chat_data["active_match"] = True
    chat_data["players"] = {}
    chat_data["reserve"] = {}
    chat_data["refund_pending"] = {}
    chat_data["paid_spot_transfers"] = {}
    update_chat_data(chat_id, chat_data)
    
    try:
        logging.info(f"[Scheduler] Попытка отправить сообщение в чат {chat_id}")
        sent_msg = await bot.send_message(
            chat_id=int(chat_id),
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=get_match_keyboard(chat_id)
        )
        chat_data["announcement_message_id"] = str(sent_msg.message_id)
        update_chat_data(chat_id, chat_data)
        logging.info(f"[Scheduler] Анонс успешно опубликован в чат {chat_id}, message_id={sent_msg.message_id}")
    except Exception as e:
        logging.error(f"[Scheduler] Ошибка при отправке анонса в чат {chat_id}: {e}", exc_info=True)

@router.callback_query(lambda c: c.data == "menu_new_game")
async def menu_new_game_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_groups = await get_user_admin_groups(bot, callback.from_user.id)
    if not admin_groups:
        await callback.answer("Сначала добавьте бота в группу и получите права администратора.", show_alert=True)
        return

    if len(admin_groups) == 1:
        await state.update_data(target_chat_id=admin_groups[0][0], group_title=admin_groups[0][1])
        await state.update_data(form_message_id=callback.message.message_id)
        await show_step(callback, state, 0)
    else:
        await callback.message.edit_text(
            "Выберите группу, для которой хотите создать матч:",
            reply_markup=get_groups_keyboard(admin_groups, "sel_new_group")
        )
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("sel_new_group_"))
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

    await state.update_data(target_chat_id=chat_id, group_title=group_title, form_message_id=callback.message.message_id)
    await show_step(callback, state, 0)
    await callback.answer()

@router.callback_query(lambda c: c.data == "form_cancel")
async def process_form_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание матча отменено.", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.callback_query(lambda c: c.data == "form_back")
async def process_form_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_step = data.get("current_step", 0)
    if current_step > 0:
        await show_step(callback, state, current_step - 1)
    await callback.answer()

@router.callback_query(lambda c: c.data == "form_forward")
async def process_form_forward(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_step = data.get("current_step", 0)
    if current_step < len(FORM_STEPS) - 1 and data.get(FORM_KEYS[current_step]):
        await show_step(callback, state, current_step + 1)
    else:
        await callback.answer("Сначала заполни текущее поле!", show_alert=True)

@router.message(NewGameForm.waiting_for_date)
@router.message(NewGameForm.waiting_for_time)
@router.message(NewGameForm.waiting_for_end_time)
@router.message(NewGameForm.waiting_for_loc_name)
@router.message(NewGameForm.waiting_for_loc_link)
@router.message(NewGameForm.waiting_for_cost)
@router.message(NewGameForm.waiting_for_phone)
@router.message(NewGameForm.waiting_for_name)
@router.message(NewGameForm.waiting_for_max_players)
@router.message(NewGameForm.waiting_for_pub_time)
async def process_form_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_step = data.get("current_step", 0)
    text = message.text.strip()

    logging.info(f"[Form] Получен ввод для шага {current_step} ({FORM_KEYS[current_step]}): '{text}'")

    if current_step == 8 and not text.isdigit():
        logging.warning(f"[Form] Шаг 8 (max_players): введено не число '{text}'")
        try:
            await message.delete()
        except Exception:
            pass
        return

    await state.update_data({FORM_KEYS[current_step]: text})

    if current_step < len(FORM_STEPS) - 1:
        logging.info(f"[Form] Переход к следующему шагу: {current_step + 1}")
        await show_step(message, state, current_step + 1, edit=False)
    else:
        logging.info("[Form] Достигнут последний шаг (время публикации). Начинаем сохранение и планирование.")
        form_data = await state.get_data()
        await state.clear()

        try:
            pub_time_str = form_data["pub_time"].strip()
            logging.info(f"[Scheduler] Попытка распарсить время публикации: '{pub_time_str}'")
            pub_dt_local = datetime.strptime(pub_time_str, "%d.%m.%Y %H:%M")
            pub_dt_local = pub_dt_local.replace(tzinfo=LOCAL_TZ)
            pub_dt_utc = pub_dt_local.astimezone(timezone.utc)
            logging.info(f"[Scheduler] Успешно распарсено. Локально: {pub_dt_local}, UTC: {pub_dt_utc}")
        except ValueError as e:
            logging.error(f"[Scheduler] Ошибка парсинга времени публикации '{form_data.get('pub_time')}': {e}")
            await message.answer("⚠️ Неверный формат даты публикации! Используйте ДД.ММ.ГГГГ ЧЧ:ММ. Нажмите «Создать игру» снова.")
            return

        chat_id = form_data["target_chat_id"]
        db_data = load_data()
        groups = db_data.setdefault("groups", {})
        chat_data = groups.setdefault(chat_id, {})
        
        chat_data["group_title"] = form_data["group_title"]
        chat_data["match_details"] = {
            "date": form_data["date"], "time": form_data["time"],
            "end_time": form_data["end_time"], "loc_name": form_data["loc_name"],
            "loc_link": form_data["loc_link"], "cost": form_data["cost"],
            "phone": form_data["phone"], "name": form_data["name"],
            "max_players": int(form_data["max_players"])
        }
        save_data(db_data)

        job_id = f"pub_match_{chat_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            send_custom_announcement,
            "date",
            run_date=pub_dt_utc,
            args=[chat_id],
            id=job_id,
            replace_existing=True
        )
        logging.info(f"[Scheduler] Задача {job_id} успешно запланирована на {pub_dt_utc} (UTC)")

        form_msg_id = form_data.get("form_message_id")
        success_text = f"✅ Матч успешно запланирован к публикации на *{form_data['pub_time']}* для группы *{escape_md(form_data['group_title'])}*!"
        if form_msg_id:
            try:
                await bot.edit_message_text(chat_id=message.chat.id, message_id=form_msg_id, text=success_text, parse_mode="Markdown")
            except Exception:
                pass
        await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())

@router.callback_query(lambda c: c.data == "menu_manage_announcements")
async def menu_manage_announcements(callback: types.CallbackQuery):
    admin_groups = await get_user_admin_groups(bot, callback.from_user.id)
    if not admin_groups:
        await callback.answer("У вас нет прав администратора ни в одной группе.", show_alert=True)
        return

    admin_chat_ids = [str(g[0]) for g in admin_groups]
    active_jobs = [j for j in scheduler.get_jobs() if j.id.startswith("pub_match_") and j.id.replace("pub_match_", "") in admin_chat_ids]

    data = load_data()
    groups = data.get("groups", {})
    published_active = [cid for cid, cdata in groups.items() if cid in admin_chat_ids and cdata.get("active_match")]

    if not active_jobs and not published_active:
        await callback.message.edit_text(
            "📭 В данный момент нет запланированных или активных матчей в ваших группах.",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for job in active_jobs:
        chat_id = job.id.replace("pub_match_", "")
        g_title = groups.get(chat_id, {}).get("group_title", chat_id)
        kb.button(text=f"🛑 Отменить план: {g_title}", callback_data=f"stop_announcement_{chat_id}")
    
    for cid in published_active:
        g_title = groups.get(cid, {}).get("group_title", cid)
        kb.button(text=f"➕ Добавить игрока в: {g_title}", callback_data=f"admin_add_player_{cid}")
        kb.button(text=f"🗑 Удалить игрока из: {g_title}", callback_data=f"admin_del_player_list_{cid}")

    kb.button(text="🔙 Назад в меню", callback_data="back_to_main_menu")
    kb.adjust(1)

    await callback.message.edit_text(
        "📢 *Управление анонсами и матчами:*",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_main_menu")
async def process_back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("stop_announcement_"))
async def process_stop_announcement(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[2]
    job_id = f"pub_match_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    data = load_data()
    if chat_id in data.get("groups", {}):
        groups = data["groups"]
        groups[chat_id].pop("match_details", None)
        groups[chat_id]["active_match"] = False
        groups[chat_id]["players"] = {}
        groups[chat_id]["reserve"] = {}
        save_data(data)

    await callback.message.edit_text(
        "🛑 Запланированная публикация отменена, данные очищены.",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer("Успешно")

@router.callback_query(lambda c: c.data and c.data.startswith("admin_add_player_"))
async def admin_add_player_start(callback: types.CallbackQuery, state: FSMContext):
    chat_id = callback.data.split("_")[3]
    await state.set_state("waiting_for_manual_player_name")
    await state.update_data(manual_chat_id=chat_id)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="menu_manage_announcements")
    
    await callback.message.edit_text(
        "👤 Введите Фамилию и Имя игрока, которого хотите добавить вручную:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

@router.message(StateFilter("waiting_for_manual_player_name"))
async def process_manual_player_name(message: types.Message, state: FSMContext):
    player_name = message.text.strip()
    await state.update_data(manual_player_name=player_name)
    await state.set_state("waiting_for_manual_player_username")

    kb = InlineKeyboardBuilder()
    kb.button(text="➡️ Пропустить (без username)", callback_data="skip_manual_username")
    kb.button(text="❌ Отмена", callback_data="menu_manage_announcements")
    kb.adjust(1)

    await message.answer(
        f"Имя: *{escape_md(player_name)}*\n\nТеперь введите `@username` игрока (например, `@durov`), чтобы его имя стало кликабельным, либо нажмите кнопку пропуска:",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@router.callback_query(lambda c: c.data == "skip_manual_username", StateFilter("waiting_for_manual_player_username"))
async def skip_manual_username(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("manual_chat_id")
    player_name = data.get("manual_player_name")
    await state.clear()

    import time
    manual_uid = f"manual_{int(time.time())}"
    
    chat_data = get_chat_data(chat_id)
    players = chat_data.setdefault("players", {})
    reserve = chat_data.setdefault("reserve", {})
    max_players = int(chat_data.get("match_details", {}).get("max_players", 12))

    if len(players) < max_players:
        players[manual_uid] = {"name": player_name, "username": None, "paid": False}
        msg_res = f"Игрок *{escape_md(player_name)}* добавлен вручную в основной состав."
    else:
        reserve[manual_uid] = {"name": player_name, "username": None, "paid": False}
        msg_res = f"Основной состав полон. Игрок *{escape_md(player_name)}* добавлен вручную в резерв."

    update_chat_data(chat_id, chat_data)
    await update_group_announcement(bot, chat_id)

    await callback.message.edit_text(f"✅ {msg_res}")
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.message(StateFilter("waiting_for_manual_player_username"))
async def process_manual_player_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("manual_chat_id")
    player_name = data.get("manual_player_name")
    await state.clear()

    username = message.text.strip().lstrip("@")
    manual_uid = f"username_{username}"

    chat_data = get_chat_data(chat_id)
    players = chat_data.setdefault("players", {})
    reserve = chat_data.setdefault("reserve", {})
    max_players = int(chat_data.get("match_details", {}).get("max_players", 12))

    if len(players) < max_players:
        players[manual_uid] = {"name": player_name, "username": username, "paid": False}
        msg_res = f"Игрок *{escape_md(player_name)}* (@{escape_md(username)}) добавлен вручную в основной состав."
    else:
        reserve[manual_uid] = {"name": player_name, "username": username, "paid": False}
        msg_res = f"Основной состав полон. Игрок *{escape_md(player_name)}* (@{escape_md(username)}) добавлен вручную в резерв."

    update_chat_data(chat_id, chat_data)
    await update_group_announcement(bot, chat_id)

    await message.answer(f"✅ {msg_res}", reply_markup=get_main_menu_keyboard())

@router.callback_query(lambda c: c.data and c.data.startswith("admin_del_player_list_"))
async def admin_del_player_list(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[4]
    chat_data = get_chat_data(chat_id)
    players = chat_data.get("players", {})
    reserve = chat_data.get("reserve", {})

    if not players and not reserve:
        await callback.answer("В матче нет участников.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for uid, pdata in players.items():
        kb.button(text=f"❌ [Осн] {pdata['name']}", callback_data=f"admindel_{chat_id}_p_{uid}")
    for uid, rdata in reserve.items():
        kb.button(text=f"❌ [Рез] {rdata['name']}", callback_data=f"admindel_{chat_id}_r_{uid}")

    kb.button(text="🔙 Назад", callback_data="menu_manage_announcements")
    kb.adjust(1)

    await callback.message.edit_text(
        "🗑 Выберите игрока для удаления из матча:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("admindel_"))
async def admin_delete_player_action(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    chat_id = parts[1]
    p_type = parts[2] 
    uid = "_".join(parts[3:]) 

    chat_data = get_chat_data(chat_id)
    players = chat_data.setdefault("players", {})
    reserve = chat_data.setdefault("reserve", {})

    target_dict = players if p_type == 'p' else reserve
    if uid not in target_dict:
        await callback.answer("Игрок не найден.", show_alert=True)
        return

    removed_player = target_dict.pop(uid)
    is_paid = removed_player.get("paid", False)
    p_name = removed_player.get("name", "Игрок")

    if p_type == 'p' and reserve:
        first_res_uid, first_res_data = next(iter(reserve.items()))
        reserve.pop(first_res_uid)
        players[first_res_uid] = first_res_data

    update_chat_data(chat_id, chat_data)
    await update_group_announcement(bot, chat_id)

    if is_paid and str(uid).isdigit():
        try:
            await bot.send_message(
                chat_id=int(uid),
                text=f"⚠️ *Внимание!*\nАдминистратор удалил вас из матча *{escape_md(p_name)}*. Не забудьте получить возврат средств!"
            )
        except Exception:
            pass

    await callback.answer(f"Игрок {p_name} удален.", show_alert=True)
    
    await admin_del_player_list(callback)
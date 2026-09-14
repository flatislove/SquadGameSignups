from datetime import datetime, timezone
from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from loader import bot, scheduler
from states import NewGameForm
from storage import load_data, save_data, get_chat_data, update_chat_data
from keyboards import get_main_menu_keyboard, get_groups_keyboard, get_match_keyboard, get_scheduled_announcements_keyboard
from utils import LOCAL_TZ, build_announcement_text, get_user_admin_groups

router = Router()

async def send_custom_announcement(bot_instance, chat_id: str):
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

@router.callback_query(lambda c: c.data == "menu_new_game")
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

    await state.update_data(target_chat_id=chat_id, group_title=group_title)
    await state.set_state(NewGameForm.waiting_for_date)
    await callback.message.edit_text(f"Создание матча для группы: *{group_title}*\n\n📅 Введите дату матча (например, 20.09.2026):", parse_mode="Markdown")
    await callback.answer()

@router.message(NewGameForm.waiting_for_date)
async def process_match_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(NewGameForm.waiting_for_time)
    await message.answer("⏰ Введите время начала матча (например, 19:00):")

@router.message(NewGameForm.waiting_for_time)
async def process_match_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await state.set_state(NewGameForm.waiting_for_end_time)
    await message.answer("🏁 Введите время окончания матча (например, 21:00):")

@router.message(NewGameForm.waiting_for_end_time)
async def process_match_end_time(message: types.Message, state: FSMContext):
    await state.update_data(end_time=message.text)
    await state.set_state(NewGameForm.waiting_for_loc_name)
    await message.answer("📍 Введите название места (например, Спортивный зал №1):")

@router.message(NewGameForm.waiting_for_loc_name)
async def process_match_loc_name(message: types.Message, state: FSMContext):
    await state.update_data(loc_name=message.text)
    await state.set_state(NewGameForm.waiting_for_loc_link)
    await message.answer("🔗 Введите ссылку на карту (например, https://maps.app.goo.gl/...):")

@router.message(NewGameForm.waiting_for_loc_link)
async def process_match_loc_link(message: types.Message, state: FSMContext):
    await state.update_data(loc_link=message.text)
    await state.set_state(NewGameForm.waiting_for_cost)
    await message.answer("💰 Введите стоимость в KZT (например, 2500):")

@router.message(NewGameForm.waiting_for_cost)
async def process_match_cost(message: types.Message, state: FSMContext):
    await state.update_data(cost=message.text)
    await state.set_state(NewGameForm.waiting_for_phone)
    await message.answer("📱 Введите номер телефона для перевода (например, +77011234567):")

@router.message(NewGameForm.waiting_for_phone)
async def process_match_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(NewGameForm.waiting_for_name)
    await message.answer("👤 Введите имя получателя (например, Владислав В.):")

@router.message(NewGameForm.waiting_for_name)
async def process_match_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(NewGameForm.waiting_for_max_players)
    await message.answer("👥 Введите максимальное количество игроков в основном составе (например, 12):")

@router.message(NewGameForm.waiting_for_max_players)
async def process_match_max_players(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (например, 12):")
        return
    await state.update_data(max_players=int(message.text))
    await state.set_state(NewGameForm.waiting_for_pub_time)
    await message.answer("🚀 Введите время публикации анонса (формат: ДД.ММ.ГГГГ ЧЧ:ММ, например, 18.09.2026 12:00):")

@router.message(NewGameForm.waiting_for_pub_time)
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

@router.callback_query(lambda c: c.data == "menu_manage_announcements")
async def menu_manage_announcements(callback: types.CallbackQuery):
    admin_groups = await get_user_admin_groups(bot, callback.from_user.id)
    if not admin_groups:
        await callback.answer("У вас нет прав администратора ни в одной группе.", show_alert=True)
        return

    admin_chat_ids = [str(g[0]) for g in admin_groups]
    
    active_jobs = []
    for job in scheduler.get_jobs():
        if job.id.startswith("pub_match_"):
            chat_id = job.id.replace("pub_match_", "")
            if chat_id in admin_chat_ids:
                active_jobs.append(job)

    if not active_jobs:
        await callback.message.edit_text(
            "📭 В данный момент нет запланированных к публикации анонсов в ваших группах.",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📢 *Список запланированных анонсов:*\nВыберите анонс, публикацию которого хотите отменить:",
        parse_mode="Markdown",
        reply_markup=get_scheduled_announcements_keyboard(active_jobs)
    )
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("stop_announcement_"))
async def process_stop_announcement(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[2]
    
    job_id = f"pub_match_{chat_id}"
    job = scheduler.get_job(job_id)
    if job:
        job.remove()

    data = load_data()
    groups = data.get("groups", {})
    if chat_id in groups:
        if "match_details" in groups[chat_id]:
            del groups[chat_id]["match_details"]
        if "active_match" in groups[chat_id]:
            groups[chat_id]["active_match"] = False
        if "players" in groups[chat_id]:
            groups[chat_id]["players"] = {}
        if "reserve" in groups[chat_id]:
            groups[chat_id]["reserve"] = {}
        save_data(data)

    await callback.message.edit_text(
        "🛑 Запланированная публикация анонса отменена.\nДанные очищены, бот больше не управляет этим матчем.",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer("Анонс отменен")
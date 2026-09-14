import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from storage import get_chat_data, update_chat_data, load_data, save_data

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

LOCAL_TZ = timezone(timedelta(hours=5))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

scheduler = AsyncIOScheduler()

class NewGameForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_end_time = State()
    waiting_for_loc_name = State()
    waiting_for_loc_link = State()
    waiting_for_cost = State()
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_pub_time = State()

def escape_md(text: str) -> str:
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text

def build_announcement_text(chat_data: dict):
    details = chat_data.get("match_details", {
        "date": "TBD",
        "time": "TBD",
        "end_time": "TBD",
        "loc_name": "TBD",
        "loc_link": "",
        "cost": "0",
        "phone": "TBD",
        "name": "TBD"
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

def get_match_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Записаться", callback_data="signup")
    builder.adjust(1)
    return builder.as_markup()

async def update_group_announcement(chat_id: str):
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
        logging.error(f"Failed to update group announcement: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        await message.answer("Бот успешно подключен к этой группе!")
    else:
        await message.answer(
            "Привет! Отправь команду /payments в личных сообщениях, чтобы управлять оплатой участников.",
            parse_mode="Markdown"
        )

@dp.message(Command("payments"))
async def cmd_payments(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("Эту команду нужно использовать в личных сообщениях с ботом.")
        return

    data = load_data()
    groups = data.get("groups", {})
    
    admin_groups = []
    for chat_id, chat_data in groups.items():
        if chat_data.get("active_match"):
            try:
                member = await bot.get_chat_member(chat_id=int(chat_id), user_id=message.from_user.id)
                if member.status in ["creator", "administrator"]:
                    group_title = chat_data.get("group_title", f"Группа {chat_id}")
                    admin_groups.append((chat_id, group_title))
            except Exception:
                continue

    if not admin_groups:
        await message.answer("У вас нет активных матчей в группах, где вы являетесь администратором.")
        return

    if len(admin_groups) == 1:
        await show_group_players_for_pay(message, admin_groups[0][0])
    else:
        builder = InlineKeyboardBuilder()
        for chat_id, title in admin_groups:
            builder.button(text=title, callback_data=f"sel_group_{chat_id}")
        builder.adjust(1)
        await message.answer("Выберите группу для управления оплатой:", reply_markup=builder.as_markup())

async def show_group_players_for_pay(message_or_callback, chat_id: str):
    chat_data = get_chat_data(chat_id)
    players = chat_data.get("players", {})
    if not players:
        text = "Список участников в этой группе пуст."
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.answer(text)
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(text)
        return

    builder = InlineKeyboardBuilder()
    for uid, pdata in players.items():
        paid_mark = "🟩" if pdata.get("paid", False) else "🟧"
        builder.button(text=f"{paid_mark} {pdata['name']}", callback_data=f"pm_pay_{chat_id}_{uid}")
    builder.adjust(1)

    text = f"Управление оплатой для группы *{chat_data.get('group_title', chat_id)}*:"
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data and c.data.startswith("sel_group_"))
async def process_select_group(callback: types.CallbackQuery):
    chat_id = callback.data.split("_")[2]
    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=callback.from_user.id)
        if member.status not in ["creator", "administrator"]:
            await callback.answer("Только администраторы могут изменять статус оплаты!", show_alert=True)
            return
    except Exception:
        await callback.answer("Ошибка проверки прав.", show_alert=True)
        return

    await show_group_players_for_pay(callback, chat_id)

@dp.message(Command("newgame"))
async def cmd_newgame(message: types.Message, state: FSMContext):
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("Команду /newgame нужно использовать внутри группы.")
        return

    chat_id = str(message.chat.id)
    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=message.from_user.id)
        if member.status not in ["creator", "administrator"]:
            await message.answer("Создавать игру могут только администраторы группы.")
            return
    except Exception:
        await message.answer("Не удалось проверить права администратора.")
        return

    await state.update_data(target_chat_id=chat_id, group_title=message.chat.title)
    await state.set_state(NewGameForm.waiting_for_date)
    await message.answer("📅 Enter match date (e.g., 20.09.2026):")

@dp.message(NewGameForm.waiting_for_date)
async def process_match_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(NewGameForm.waiting_for_time)
    await message.answer("⏰ Enter match start time (e.g., 19:00):")

@dp.message(NewGameForm.waiting_for_time)
async def process_match_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await state.set_state(NewGameForm.waiting_for_end_time)
    await message.answer("🏁 Enter match end time (e.g., 21:00):")

@dp.message(NewGameForm.waiting_for_end_time)
async def process_match_end_time(message: types.Message, state: FSMContext):
    await state.update_data(end_time=message.text)
    await state.set_state(NewGameForm.waiting_for_loc_name)
    await message.answer("📍 Enter location name (e.g., Sports Hall #1):")

@dp.message(NewGameForm.waiting_for_loc_name)
async def process_match_loc_name(message: types.Message, state: FSMContext):
    await state.update_data(loc_name=message.text)
    await state.set_state(NewGameForm.waiting_for_loc_link)
    await message.answer("🔗 Enter location URL/link (e.g., https://maps.app.goo.gl/...):")

@dp.message(NewGameForm.waiting_for_loc_link)
async def process_match_loc_link(message: types.Message, state: FSMContext):
    await state.update_data(loc_link=message.text)
    await state.set_state(NewGameForm.waiting_for_cost)
    await message.answer("💰 Enter match cost in KZT (e.g., 2500):")

@dp.message(NewGameForm.waiting_for_cost)
async def process_match_cost(message: types.Message, state: FSMContext):
    await state.update_data(cost=message.text)
    await state.set_state(NewGameForm.waiting_for_phone)
    await message.answer("📱 Enter phone number for payment transfer (e.g., +77011234567):")

@dp.message(NewGameForm.waiting_for_phone)
async def process_match_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(NewGameForm.waiting_for_name)
    await message.answer("👤 Enter recipient name (e.g., Vladislav V.):")

@dp.message(NewGameForm.waiting_for_name)
async def process_match_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(NewGameForm.waiting_for_pub_time)
    await message.answer("🚀 Enter publication time (format: DD.MM.YYYY HH:MM, e.g., 18.09.2026 12:00):")

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
        await message.answer("Invalid date format! Please use DD.MM.YYYY HH:MM. Run /newgame again.")
        return

    chat_id = form_data["target_chat_id"]
    
    data = load_data()
    groups = data.setdefault("groups", {})
    chat_data = groups.setdefault(chat_id, {})
    
    chat_data["group_title"] = form_data["group_title"]
    chat_data["match_details"] = {
        "date": form_data["date"],
        "time": form_data["time"],
        "end_time": form_data["end_time"],
        "loc_name": form_data["loc_name"],
        "loc_link": form_data["loc_link"],
        "cost": form_data["cost"],
        "phone": form_data["phone"],
        "name": form_data["name"]
    }
    save_data(data)

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

    await message.answer(f"Match announcement successfully scheduled for {pub_time_str}!")

async def send_custom_announcement(chat_id: str):
    chat_data = get_chat_data(chat_id)
    chat_data["active_match"] = True
    chat_data["players"] = {}
    update_chat_data(chat_id, chat_data)
    
    try:
        sent_msg = await bot.send_message(
            chat_id=int(chat_id),
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=get_match_keyboard()
        )
        chat_data["announcement_message_id"] = str(sent_msg.message_id)
        update_chat_data(chat_id, chat_data)
    except Exception as e:
        logging.error(f"Failed to send scheduled announcement to {chat_id}: {e}")

@dp.message(Command("cancel_schedule"))
async def cmd_cancel_schedule(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    chat_id = str(message.chat.id)

    job_id = f"pub_match_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        await message.answer("Automated schedule has been cancelled.")
    else:
        await message.answer("No active schedule found.")

@dp.callback_query(lambda c: c.data == "signup")
async def process_signup(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    user = callback.from_user
    user_id = str(user.id)
    full_name = user.full_name
    
    chat_data = get_chat_data(chat_id)
    
    if not chat_data.get("active_match"):
        await callback.answer("No active match at the moment!", show_alert=True)
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
        logging.error(f"Failed to update message on signup: {e}")
        
    await callback.answer(status_text)

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

        await update_group_announcement(chat_id)

        players_sub = chat_data.get("players", {})
        builder = InlineKeyboardBuilder()
        for uid, pdata in players_sub.items():
            paid_mark = "🟩" if pdata.get("paid", False) else "🟧"
            builder.button(text=f"{paid_mark} {pdata['name']}", callback_data=f"pm_pay_{chat_id}_{uid}")
        builder.adjust(1)

        try:
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except Exception:
            pass
            
    await callback.answer("Статус обновлен")

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Starting bot and scheduler...")
    
    scheduler.start()
    
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
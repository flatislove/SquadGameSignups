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

# Ваш часовой пояс (UTC+5)
LOCAL_TZ = timezone(timedelta(hours=5))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

scheduler = AsyncIOScheduler()

class NewGameForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_loc_name = State()
    waiting_for_loc_link = State()
    waiting_for_cost = State()
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_pub_time = State()

def save_linked_chat(chat_id: str):
    data = load_data()
    data["linked_chat_id"] = chat_id
    save_data(data)

def get_linked_chat():
    data = load_data()
    return data.get("linked_chat_id")

def build_announcement_text(chat_data: dict):
    details = chat_data.get("match_details", {
        "date": "TBD",
        "time": "TBD",
        "loc_name": "TBD",
        "loc_link": "",
        "cost": "0",
        "phone": "TBD",
        "name": "TBD"
    })
    
    players = chat_data.get("players", {})
    players_list_text = "\n".join([f"{i+1}. @{name}" for i, (_, name) in enumerate(players.items())])
    if not players_list_text:
        players_list_text = "No players yet."
        
    loc_display = f"[{details['loc_name']}]({details['loc_link']})" if details.get('loc_link') else details['loc_name']
    
    return (
        f"🏐 *Match Announcement*\n\n"
        f"📅 *Дата:* {details['date']}\n"
        f"⏰ *Время:* {details['time']}\n"
        f"📍 *Место:* {loc_display}\n"
        f"💰 *Стоимость:* {details['cost']} KZT\n"
        f"💳 *Перевод:* `{details['phone']}` ({details['name']})\n\n"
        f"*Registered players ({len(players)}):*\n{players_list_text}"
    )

@dp.message(lambda message: message.chat.type in ["group", "supergroup"])
async def group_activity_handler(message: types.Message):
    save_linked_chat(str(message.chat.id))

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        save_linked_chat(str(message.chat.id))
        await message.answer("Group successfully linked!")
    else:
        linked = get_linked_chat()
        await message.answer(
            f"Hello! I am *Squad Game Signups*.\nLinked group ID: `{linked}`",
            parse_mode="Markdown"
        )

@dp.message(Command("newgame"))
async def cmd_newgame(message: types.Message, state: FSMContext):
    chat_id = get_linked_chat()
    if not chat_id:
        await message.answer("No linked group found. Please send any message in your Telegram group first.")
        return

    await state.set_state(NewGameForm.waiting_for_date)
    await message.answer("📅 Enter match date (e.g., 20.09.2026):")

@dp.message(NewGameForm.waiting_for_date)
async def process_match_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(NewGameForm.waiting_for_time)
    await message.answer("⏰ Enter match time (e.g., 19:00):")

@dp.message(NewGameForm.waiting_for_time)
async def process_match_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
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

    chat_id = get_linked_chat()
    chat_data = get_chat_data(chat_id)
    
    chat_data["match_details"] = {
        "date": form_data["date"],
        "time": form_data["time"],
        "loc_name": form_data["loc_name"],
        "loc_link": form_data["loc_link"],
        "cost": form_data["cost"],
        "phone": form_data["phone"],
        "name": form_data["name"]
    }
    update_chat_data(chat_id, chat_data)

    job_id = f"pub_match_{chat_id}_{int(pub_dt_utc.timestamp())}"
    scheduler.add_job(
        lambda: asyncio.create_task(send_custom_announcement(chat_id)),
        "date",
        run_date=pub_dt_utc,
        id=job_id,
        replace_existing=True
    )

    await message.answer(f"Match announcement successfully scheduled for {pub_time_str}!")

async def send_custom_announcement(chat_id: str):
    chat_data = get_chat_data(chat_id)
    chat_data["active_match"] = True
    chat_data["players"] = {}
    update_chat_data(chat_id, chat_data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Sign Up", callback_data="signup")
    
    try:
        await bot.send_message(
            chat_id=int(chat_id),
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logging.error(f"Failed to send scheduled announcement to {chat_id}: {e}")

@dp.message(Command("cancel_schedule"))
async def cmd_cancel_schedule(message: types.Message):
    chat_id = get_linked_chat()
    if not chat_id:
        await message.answer("No linked group found.")
        return

    # Удаляем все запланированные задания для этого чата
    removed = False
    for job in scheduler.get_jobs():
        if job.id.startswith(f"pub_match_{chat_id}"):
            scheduler.remove_job(job.id)
            removed = True

    if removed:
        await message.answer("Automated schedule has been cancelled.")
    else:
        await message.answer("No active schedule found.")

@dp.callback_query(lambda c: c.data == "signup")
async def process_signup(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    user = callback.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    
    chat_data = get_chat_data(chat_id)
    
    if not chat_data.get("active_match"):
        await callback.answer("No active match at the moment!", show_alert=True)
        return
    
    players = chat_data.setdefault("players", {})
    
    if user_id in players:
        del players[user_id]
        status_text = "You have been removed from the list."
    else:
        players[user_id] = username
        status_text = "Successfully registered!"
        
    update_chat_data(chat_id, chat_data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Sign Up", callback_data="signup")
    
    try:
        await callback.message.edit_text(
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=builder.as_markup()
        )
    except Exception:
        pass
        
    await callback.answer(status_text)

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
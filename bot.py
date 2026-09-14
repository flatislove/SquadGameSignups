import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from storage import get_chat_data, update_chat_data, load_data, save_data

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

scheduler = AsyncIOScheduler()

class NewGameForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_location = State()
    waiting_for_cost = State()

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
        "location": "TBD",
        "cost": "TBD"
    })
    
    players = chat_data.get("players", {})
    players_list_text = "\n".join([f"{i+1}. @{name}" for i, (_, name) in enumerate(players.items())])
    if not players_list_text:
        players_list_text = "No players yet."
        
    return (
        f"🏐 **Match Announcement**\n\n"
        f"📅 **Дата:** {details['date']}\n"
        f"⏰ **Время:** {details['time']}\n"
        f"📍 **Место:** {details['location']}\n"
        f"💰 **Стоимость:** {details['cost']}\n\n"
        f"**Registered players ({len(players)}):**\n{players_list_text}"
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
            f"Hello! I am **Squad Game Signups**.\nLinked group ID: `{linked}`"
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
    await state.set_state(NewGameForm.waiting_for_location)
    await message.answer("📍 Enter match location (e.g., Sports Hall #1):")

@dp.message(NewGameForm.waiting_for_location)
async def process_match_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(NewGameForm.waiting_for_cost)
    await message.answer("💰 Enter match cost (e.g., 15 BYN):")

@dp.message(NewGameForm.waiting_for_cost)
async def process_match_cost(message: types.Message, state: FSMContext):
    form_data = await state.get_data()
    cost = message.text
    await state.clear()

    chat_id = get_linked_chat()
    chat_data = get_chat_data(chat_id)
    
    chat_data["active_match"] = True
    chat_data["players"] = {}
    chat_data["match_details"] = {
        "date": form_data["date"],
        "time": form_data["time"],
        "location": form_data["location"],
        "cost": cost
    }
    update_chat_data(chat_id, chat_data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Sign Up", callback_data="signup")
    
    try:
        await bot.send_message(
            chat_id=int(chat_id),
            text=build_announcement_text(chat_data),
            reply_markup=builder.as_markup()
        )
        await message.answer("Match successfully created and published in the group!")
    except Exception as e:
        await message.answer(f"Failed to send message to group: {e}")

@dp.message(Command("set_schedule"))
async def cmd_set_schedule(message: types.Message):
    await message.answer("Scheduled automatic announcements use default or last configured details. Use /newgame in PM for custom interactive setup.")

@dp.message(Command("cancel_schedule"))
async def cmd_cancel_schedule(message: types.Message):
    chat_id = get_linked_chat()
    if not chat_id:
        await message.answer("No linked group found.")
        return

    job_id = f"game_match_{chat_id}"
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
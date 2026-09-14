import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from storage import get_chat_data, update_chat_data

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Hello! I am **Squad Game Signups** — a bot for organizing match signups and managing registrations."
    )

@dp.message(Command("newgame"))
async def cmd_newgame(message: types.Message):
    chat_id = str(message.chat.id)
    chat_data = get_chat_data(chat_id)
    
    chat_data["active_match"] = True
    chat_data["players"] = {}
    update_chat_data(chat_id, chat_data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Sign Up", callback_data="signup")
    
    await message.answer(
        "🏐 **New Match Announced!**\nClick the button below to secure your spot.",
        reply_markup=builder.as_markup()
    )

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
        status_text = "You are successfully registered!"
        
    update_chat_data(chat_id, chat_data)
    
    players_list_text = "\n".join([f"{i+1}. @{name}" for i, (_, name) in enumerate(players.items())])
    if not players_list_text:
        players_list_text = "No players yet."
        
    text = (
        f"🏐 **New Match Announced!**\n\n"
        f"**Registered players ({len(players)}):**\n{players_list_text}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Sign Up", callback_data="signup")
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
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
    print("Starting bot...")
    
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
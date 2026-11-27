import logging
from telegram import Update
from telegram.ext import ContextTypes, ChatMemberHandler
from backend.core.db import get_db

logger = logging.getLogger(__name__)

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tracks bot status in chats via my_chat_member updates."""
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    new_member = result.new_chat_member
    
    if chat.type in ["group", "supergroup"]:
        db = get_db()
        is_bot = new_member.user.id == context.bot.id
        if is_bot:
            status = new_member.status
            is_active = status in ["member", "administrator"]
            
            logger.info(f"🤖 Bot membership updated in chat {chat.id} ('{chat.title}'): status={status}, active={is_active}")
            
            try:
                db.table("groups").upsert({
                    "chat_id": chat.id,
                    "title": chat.title or "Волейбольная группа",
                    "is_active": is_active
                }, on_conflict="chat_id").execute()
            except Exception as e:
                logger.error(f"Failed to upsert group {chat.id} in DB: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    if chat_type != "private":
        return

    web_app_url = f"https://t.me/{context.bot.username}"
    # If start argument contains game id (e.g. game_<uuid>), we can pass it or handle on frontend
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏐 Управлять записью",
                web_app=WebAppInfo(url=f"https://flatislove.github.io/SquadGameSignups/")
            )
        ]
    ]
    await update.message.reply_text(
        "Привет! Нажми на кнопку ниже, чтобы открыть мини-приложение для записи на волейбол или создания анонсов:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from telegram.ext import Application, CommandHandler, ChatMemberHandler, filters

from backend.core.config import settings
from backend.core.db import init_db
from backend.core.scheduler import init_scheduler, scheduler
from backend.core.telegram_gateway import telegram_gateway
from backend.registry import register_all_routers
from backend.modules.groups.router import track_chats, start_command

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

telegram_application = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_application
    logger.info("==> Starting FastAPI application & Telegram Bot lifespan...")
    
    # Initialize DB & Scheduler
    init_db()
    init_scheduler()

    # Initialize Telegram Bot Application
    if settings.BOT_TOKEN:
        telegram_application = Application.builder().token(settings.BOT_TOKEN).build()
        
        # Register bot handlers
        telegram_application.add_handler(CommandHandler("start", start_command, filters=filters.ChatType.PRIVATE))
        telegram_application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

        # Initialize and start bot in background
        await telegram_application.initialize()
        await telegram_application.start()
        
        if telegram_application.updater:
            await telegram_application.updater.start_polling(allowed_updates=["message", "my_chat_member"])

        telegram_gateway.set_bot(telegram_application.bot)
        logger.info("==> Telegram Bot successfully started via polling in FastAPI lifespan")
    else:
        logger.warning("⚠️ BOT_TOKEN is not set. Telegram bot will not start.")

    yield

    logger.info("==> Shutting down FastAPI application & Telegram Bot...")
    if telegram_application:
        if telegram_application.updater:
            await telegram_application.updater.stop()
        await telegram_application.stop()
        await telegram_application.shutdown()
    if scheduler.running:
        scheduler.shutdown()

app = FastAPI(
    title="SquadGameSignups API",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register all API routers
register_all_routers(app)

@app.get("/ping")
async def ping():
    return {"status": "alive", "service": "SquadGameSignups backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=10000, reload=False)

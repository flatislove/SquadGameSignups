import asyncio
import logging
import os
import sys
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from handlers.game import router as game_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not BOT_TOKEN:
        logging.error("❌ Не задана переменная окружения BOT_TOKEN!")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    scheduler = AsyncIOScheduler(timezone=ZoneInfo('Asia/Almaty'))
    scheduler.start()
    
    dp.workflow_data.update(scheduler=scheduler)
    dp.include_router(game_router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("==> Бот запущен и готов к работе")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import logging
import os
from aiohttp import web
from dotenv import load_dotenv

from loader import bot, dp, scheduler

from routers.base import router as base_router
from routers.admin_game import router as admin_game_router
from routers.payments import router as payments_router
from routers.match_flow import router as match_flow_router

load_dotenv()
PORT = int(os.getenv("PORT", 8080))

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
    
    # Регистрация всех роутеров в диспетчере
    dp.include_router(base_router)
    dp.include_router(admin_game_router)
    dp.include_router(payments_router)
    dp.include_router(match_flow_router)
    
    scheduler.start()
    
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
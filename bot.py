import asyncio
import http.server
import logging
import os
import socketserver
import sys
import threading
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from handlers.game import (
    DATE, TIME, END_TIME, LOC_NAME, LOC_LINK,
    COST, PHONE, NAME, MAX_PLAYERS, PUB_TIME,
    start_form, process_date, process_time, process_end_time,
    process_loc_name, process_loc_link, process_cost, process_phone,
    process_name, process_max_players, process_pub_time, cancel
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# Запускаем простейший HTTP-сервер в фоновом потоке, чтобы Render видел открытый порт
def run_dummy_server():
    class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is alive!")
        
        def log_message(self, format, *args):
            # Отключаем лишний лог HTTP-запросов, чтобы не засорять консоль
            pass

    try:
        with socketserver.TCPServer(("", PORT), HealthCheckHandler) as httpd:
            logging.info(f"==> HTTP-сервер запущен на порту {PORT}")
            httpd.serve_forever()
    except Exception as e:
        logging.error(f"❌ Ошибка запуска HTTP-сервера: {e}")

async def main_async():
    if not BOT_TOKEN:
        logging.error("❌ Не задана переменная окружения BOT_TOKEN!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newgame", start_form)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_end_time)],
            LOC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_loc_name)],
            LOC_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_loc_link)],
            COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_cost)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
            MAX_PLAYERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_max_players)],
            PUB_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pub_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    logging.info("==> Бот запущен и готов к работе")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    stop_event = asyncio.Event()
    await stop_event.wait()

def main():
    # Запускаем веб-сервер для Render в отдельном потоке
    server_thread = threading.Thread(target=run_dummy_server, daemon=True)
    server_thread.start()

    # Запускаем бота в главном потоке через Python 3.14 совместимый asyncio.run
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
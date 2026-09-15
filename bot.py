import asyncio
import http.server
import json
import logging
import os
import socketserver
import sys
import threading
from urllib.parse import parse_qs, urlparse
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from handlers.game import (
    DATE, TIME, END_TIME, LOC_NAME, LOC_LINK,
    COST, PHONE, NAME, MAX_PLAYERS, PUB_TIME,
    start_form, process_date, process_time, process_end_time,
    process_loc_name, process_loc_link, process_cost, process_phone,
    process_name, process_max_players, process_pub_time, cancel,
    ACTIVE_GAMES
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

def run_web_server():
    class WebAppHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory="docs", **kwargs)

        def do_GET(self):
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query = parse_qs(parsed_path.query)

            # API: Проверка статуса пользователя для Web App
            if path == "/api/user-status":
                user_id = int(query.get("user_id", [0])[0])
                game_data = next(iter(ACTIVE_GAMES.values()), None)
                
                if not game_data:
                    response = {"status": "not_registered", "message": "Активных игр пока нет.", "payment_text": ""}
                else:
                    main_list = game_data["main_list"]
                    reserve_list = game_data["reserve_list"]
                    payments = game_data["payments"]

                    if user_id in main_list:
                        is_paid = payments.get(user_id, False)
                        response = {
                            "status": "main",
                            "message": "✅ Вы записаны в основной список.",
                            "payment_text": "💰 Оплата подтверждена." if is_paid else "⚠️ Оплата не найдена либо еще не подтверждена администратором."
                        }
                    elif user_id in reserve_list:
                        response = {
                            "status": "reserve",
                            "message": "📌 Вы находитесь в резерве в порядке очереди. Оплата пока не требуется.",
                            "payment_text": ""
                        }
                    else:
                        response = {"status": "not_registered", "message": "Вы не записаны на эту игру.", "payment_text": ""}

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                return

            return super().do_GET()

        def do_POST(self):
            parsed_path = urlparse(self.path)
            
            # API: Запись игрока через Web App
            if parsed_path.path == "/api/signup":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode("utf-8"))
                    user_id = int(data.get("user_id"))

                    if ACTIVE_GAMES:
                        chat_id = list(ACTIVE_GAMES.keys())[0]
                        game = ACTIVE_GAMES[chat_id]
                    else:
                        chat_id = 0
                        ACTIVE_GAMES[chat_id] = {"max_players": 12, "main_list": [], "reserve_list": [], "user_names": {}, "payments": {}}
                        game = ACTIVE_GAMES[chat_id]

                    main_list = game["main_list"]
                    reserve_list = game["reserve_list"]
                    max_players = int(game["max_players"])
                    payments = game["payments"]

                    if user_id not in main_list and user_id not in reserve_list:
                        if len(main_list) < max_players:
                            main_list.append(user_id)
                            payments[user_id] = False
                            result = {"success": True, "list": "main"}
                        else:
                            reserve_list.append(user_id)
                            result = {"success": True, "list": "reserve"}
                    else:
                        result = {"success": True, "message": "Already registered"}

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        def log_message(self, format, *args):
            pass

    try:
        with socketserver.TCPServer(("", PORT), WebAppHandler) as httpd:
            logging.info(f"==> Веб-сервер и API запущены на порту {PORT}")
            httpd.serve_forever()
    except Exception as e:
        logging.error(f"❌ Ошибка запуска веб-сервера: {e}")

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
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
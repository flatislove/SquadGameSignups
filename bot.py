import asyncio
import http.server
import json
import logging
import os
import socketserver
import sys
import threading
from urllib.parse import parse_qs, urlparse
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from handlers.game import ACTIVE_GAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# Глобальная ссылка на приложение Telegram бота для использования в веб-сервере
telegram_application = None

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

            # API: Получение списка групп, где пользователь является администратором
            if path == "/api/admin-chats":
                user_id = int(query.get("user_id", [0])[0])
                admin_chats = []
                
                try:
                    if telegram_application:
                        loop = telegram_application.loop
                        
                        async def fetch_admin_chats():
                            result = []
                            # Проверяем все чаты, которые известны боту или сохранены
                            chats_to_check = list(ACTIVE_GAMES.keys())
                            # Если активных игр нет, можно попытаться вернуть базовый список или пустой
                            for chat_id in chats_to_check:
                                if chat_id == 0:
                                    continue
                                try:
                                    member = await telegram_application.bot.get_chat_member(chat_id, user_id)
                                    if member.status in ["creator", "administrator"]:
                                        chat = await telegram_application.bot.get_chat(chat_id)
                                        result.append({"id": chat_id, "title": chat.title or f"Группа {chat_id}"})
                                except Exception:
                                    pass
                            return result

                        future = asyncio.run_coroutine_threadsafe(fetch_admin_chats(), loop)
                        admin_chats = future.result(timeout=5)
                except Exception as e:
                    logging.error(f"Ошибка получения админ-чатов: {e}")

                # Если ничего не нашлось автоматически через Telegram API, даем заглушку или просим добавить бота
                if not admin_chats:
                    # Для удобства тестирования можно оставить чаты из ACTIVE_GAMES или дефолтный вариант
                    admin_chats = [{"id": cid, "title": f"Волейбольный чат ({cid})"} for cid in ACTIVE_GAMES.keys() if cid != 0]
                    if not admin_chats:
                        admin_chats = [] # Пустой список стимулирует корректный вывод на фронтенде

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(admin_chats, ensure_ascii=False).encode("utf-8"))
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

            # API: Создание игры через веб-форму в Web App
            if parsed_path.path == "/api/create-game":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode("utf-8"))
                    chat_id = int(data.get("chat_id", 0))
                    
                    game_data = {
                        "date": data.get("date"),
                        "time": data.get("time"),
                        "end_time": data.get("end_time"),
                        "loc_name": data.get("loc_name"),
                        "loc_link": data.get("loc_link"),
                        "cost": data.get("cost"),
                        "phone": data.get("phone"),
                        "name": data.get("name"),
                        "max_players": int(data.get("max_players", 12))
                    }

                    # Сохраняем игру в память
                    ACTIVE_GAMES[chat_id] = {
                        "max_players": game_data["max_players"],
                        "main_list": [],
                        "reserve_list": [],
                        "user_names": {},
                        "payments": {},
                        "game_info": game_data
                    }

                    # Ссылка на ваш Web App для управления записью
                    web_app_url = "https://flatislove.github.io/SquadGameSignups/"
                    keyboard = [[InlineKeyboardButton("🏐 Управлять записью", web_app=WebAppInfo(url=web_app_url))]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    announcement_text = (
                        f"🏐 **Волейбольный матч!**\n\n"
                        f"📅 **Дата:** {game_data['date']}\n"
                        f"⏰ **Время:** {game_data['time']} - {game_data['end_time']}\n"
                        f"📍 **Площадка:** {game_data['loc_name']}\n"
                        f"🗺 [Ссылка на карту]({game_data['loc_link']})\n"
                        f"💰 **Стоимость:** {game_data['cost']}\n"
                        f"👥 **Максимум игроков:** {game_data['max_players']}\n"
                        f"👤 **Организатор:** {game_data['name']} ({game_data['phone']})"
                    )

                    if telegram_application:
                        async def send_msg():
                            await telegram_application.bot.send_message(
                                chat_id=chat_id,
                                text=announcement_text,
                                reply_markup=reply_markup,
                                parse_mode="Markdown"
                            )
                        asyncio.run_coroutine_threadsafe(send_msg(), telegram_application.loop)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
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
    global telegram_application

    if not BOT_TOKEN:
        logging.error("❌ Не задана переменная окружения BOT_TOKEN!")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    telegram_application = application

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
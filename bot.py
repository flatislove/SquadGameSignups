import json
import logging
import threading
import asyncio
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен вашего бота
TOKEN = "7916527503:AAH1V62yU8_r8a-i4Q2x5Kz3h6J1m8n9f0"

# Жестко привязанная волейбольная группа
MY_GROUP_ID = -1004349786806

# Глобальное хранилище активных игр
ACTIVE_GAMES = {}

telegram_application = None


# --- Telegram Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственная команда и открытие Web App"""
    web_app_url = "https://squadgamesignups.onrender.com"
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏐 Управлять записью", 
                web_app=WebAppInfo(url=web_app_url)
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Привет! Нажми на кнопку ниже, чтобы открыть мини-приложение для записи на волейбол или создания анонсов:",
        reply_markup=reply_markup
    )


# --- HTTP-сервер для API и Web App ---
class WebAppAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Раздаем статические файлы из папки docs
        super().__init__(*args, directory="docs", **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        # API: Проверка статуса пользователя
        if path == "/api/user-status":
            user_id = int(query.get("user_id", [0])[0])
            
            game_data = ACTIVE_GAMES.get(MY_GROUP_ID)
            
            if not game_data:
                response = {
                    "status": "not_registered",
                    "message": "Активных игр пока нет. Ожидайте анонса!"
                }
            else:
                main_list = game_data.get("main_list", [])
                reserve_list = game_data.get("reserve_list", [])
                
                if user_id in main_list:
                    response = {
                        "status": "main",
                        "message": "✅ Вы записаны в ОСНОВНОЙ состав!"
                    }
                elif user_id in reserve_list:
                    response = {
                        "status": "reserve",
                        "message": "⚠️ Мест нет, вы находитесь в РЕЗЕРВЕ."
                    }
                else:
                    response = {
                        "status": "not_registered",
                        "message": f"Свободных мест: {max(0, game_data['max_players'] - len(main_list))}"
                    }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return

        # API: Получение списка админ-чатов
        elif path == "/api/admin-chats":
            user_id = int(query.get("user_id", [0])[0])
            admin_chats = []
            
            try:
                if telegram_application and MY_GROUP_ID != 0:
                    loop = telegram_application.loop
                    
                    async def check_admin():
                        try:
                            member = await telegram_application.bot.get_chat_member(MY_GROUP_ID, user_id)
                            if member.status in ["creator", "administrator"]:
                                chat = await telegram_application.bot.get_chat(MY_GROUP_ID)
                                return [{"id": MY_GROUP_ID, "title": chat.title or "Волейбольная группа"}]
                        except Exception as e:
                            logger.error(f"Не удалось проверить админа в группе {MY_GROUP_ID}: {e}")
                        return []

                    future = asyncio.run_coroutine_threadsafe(check_admin(), loop)
                    admin_chats = future.result(timeout=5)
            except Exception as e:
                logger.error(f"Ошибка получения админ-чатов: {e}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(admin_chats, ensure_ascii=False).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = {}

        # API: Регистрация пользователя на игру
        if path == "/api/signup":
            user_id = data.get("user_id")
            success = False
            
            if MY_GROUP_ID in ACTIVE_GAMES:
                game = ACTIVE_GAMES[MY_GROUP_ID]
                main_list = game["main_list"]
                reserve_list = game["reserve_list"]
                
                if user_id not in main_list and user_id not in reserve_list:
                    if len(main_list) < game["max_players"]:
                        main_list.append(user_id)
                    else:
                        reserve_list.append(user_id)
                    success = True

            response = {"success": success}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return

        # API: Создание игры / анонса из веб-формы
        elif path == "/api/create-game":
            chat_id = int(data.get("chat_id", MY_GROUP_ID))
            success = True
            
            try:
                max_p = int(data.get('max_players', 12))
            except ValueError:
                max_p = 12

            ACTIVE_GAMES[chat_id] = {
                "max_players": max_p,
                "main_list": [],
                "reserve_list": [],
                "game_info": data
            }

            if telegram_application:
                loop = telegram_application.loop
                async def send_now():
                    text = (
                        f"🏐 **Волейбольный матч!**\n\n"
                        f"📅 **Дата:** {data.get('date', 'Уточняется')}\n"
                        f"⏰ **Время:** {data.get('time', '')} - {data.get('end_time', '')}\n"
                        f"📍 **Площадка:** {data.get('loc_name', 'Уточняется')}\n"
                        f"🗺 [Ссылка на карту]({data.get('loc_link', '#')})\n"
                        f"💰 **Стоимость:** {data.get('cost', 'Бесплатно')}\n"
                        f"👥 **Максимум игроков:** {data.get('max_players', 'Не указано')}\n"
                        f"👤 **Организатор:** {data.get('name', '')} ({data.get('phone', '')})"
                    )
                    web_app_url = "https://squadgamesignups.onrender.com"
                    keyboard = [[InlineKeyboardButton(text="🏐 Управлять записью", web_app=WebAppInfo(url=web_app_url))]]
                    await telegram_application.bot.send_message(
                        chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                    )

                asyncio.run_coroutine_threadsafe(send_now(), loop)

            response = {"success": success}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_http_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, WebAppAPIHandler)
    logger.info("==> Веб-сервер и API запущены на порту 10000")
    httpd.serve_forever()


def main():
    global telegram_application
    
    # Инициализация бота
    telegram_application = Application.builder().token(TOKEN).build()

    # Регистрация команд
    telegram_application.add_handler(CommandHandler("start", start))

    # Запуск HTTP-сервера в отдельном потоке
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()

    logger.info("==> Бот запущен и готов к работе")
    
    # Корректная инициализация цикла событий для Python 3.14+
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    telegram_application.run_polling()


if __name__ == "__main__":
    main()
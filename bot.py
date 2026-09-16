import json
import logging
import threading
import asyncio
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, filters

# Настройка максимально подробного логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
MY_GROUP_ID = -1004349786806
ACTIVE_GAMES = {}

telegram_application = None
bot_loop = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    logger.info(f"🤖 Получена команда /start из чата типа: {chat_type} (ID: {update.effective_chat.id})")
    
    if chat_type != "private":
        logger.info("🚫 Команда /start вызвана в группе — игнорируем отправку Web App кнопки.")
        return

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
    logger.info("✅ Приветственное сообщение с Web App кнопкой успешно отправлено в ЛС.")


class WebAppAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="docs", **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        logger.info(f"🌐 [GET] Входящий запрос -> Путь: {path} | Параметры: {query}")

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
            logger.info(f"📤 [GET] Ответ на /api/user-status для user_id={user_id}: {response}")
            return

        elif path == "/api/admin-chats":
            user_id = int(query.get("user_id", [0])[0])
            admin_chats = []
            
            try:
                if telegram_application and bot_loop and MY_GROUP_ID != 0:
                    async def check_admin():
                        try:
                            member = await telegram_application.bot.get_chat_member(MY_GROUP_ID, user_id)
                            logger.info(f"🛡 Проверка прав админа для user_id={user_id} в чате {MY_GROUP_ID}. Статус: {member.status}")
                            if member.status in ["creator", "administrator"]:
                                chat = await telegram_application.bot.get_chat(MY_GROUP_ID)
                                return [{"id": MY_GROUP_ID, "title": chat.title or "Волейбольная группа"}]
                        except Exception as e:
                            logger.error(f"❌ Ошибка внутри check_admin для {user_id}: {e}")
                        return []

                    future = asyncio.run_coroutine_threadsafe(check_admin(), bot_loop)
                    admin_chats = future.result(timeout=5)
            except Exception as e:
                logger.error(f"❌ Общая ошибка получения админ-чатов: {e}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(admin_chats, ensure_ascii=False).encode("utf-8"))
            logger.info(f"📤 [GET] Ответ на /api/admin-chats для user_id={user_id}: {admin_chats}")
            return

        elif path == "/ping":
            response = {"status": "alive", "timestamp": datetime.now().isoformat()}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        logger.info(f"📥 [POST] Входящий запрос -> Путь: {path}")
        logger.info(f"📦 [POST] Заголовки: {dict(self.headers)}")
        logger.info(f"📦 [POST] Тело запроса (Raw): {body.decode('utf-8', errors='ignore')}")

        try:
            data = json.loads(body.decode('utf-8'))
            logger.info(f"🔍 [POST] Успешно разобран JSON: {data}")
        except Exception as e:
            logger.error(f"❌ [POST] Ошибка разбора JSON: {e}")
            data = {}

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
            logger.info(f"📤 [POST] Ответ на /api/signup: {response}")
            return

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
            logger.info(f"📝 Игра сохранена в памяти для чата {chat_id}. Всего активных игр: {len(ACTIVE_GAMES)}")

            if telegram_application and bot_loop:
                async def send_now():
                    try:
                        publish_time = data.get('publish_time', 'now')
                        logger.info(f"🚀 Запуск отправки анонса в Telegram. Чат ID: {chat_id}, Время публикации: {publish_time}")
                        
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
                        
                        logger.info(f"📡 Вызов telegram_application.bot.send_message в чат {chat_id}...")
                        msg = await telegram_application.bot.send_message(
                            chat_id=chat_id, 
                            text=text, 
                            reply_markup=InlineKeyboardMarkup(keyboard), 
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ УСПЕХ! Анонс отправлен в Telegram. Message ID: {msg.message_id}")
                    except Exception as e:
                        logger.exception(f"❌ КРИТИЧЕСКАЯ ОШИБКА отправки сообщения в Telegram-чат {chat_id}:")

                asyncio.run_coroutine_threadsafe(send_now(), bot_loop)
            else:
                logger.error("❌ ОШИБКА: telegram_application или bot_loop не инициализированы!")

            response = {"success": success}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            logger.info(f"📤 [POST] Ответ на /api/create-game отправлен клиенту: {response}")
            return

        self.send_response(404)
        self.end_headers()
        logger.warning(f"⚠️ [POST] Неизвестный путь: {path}")

    def do_OPTIONS(self, *args, **kwargs):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_http_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, WebAppAPIHandler)
    logger.info("==> Веб-сервер и HTTP API запущены на порту 10000")
    httpd.serve_forever()


def main():
    global telegram_application, bot_loop
    
    if not TOKEN:
        logger.error("❌ Не найден токен бота! Убедитесь, что переменная окружения BOT_TOKEN установлена на Render.")
        return

    telegram_application = Application.builder().token(TOKEN).build()
    # Регистрируем /start только для личных чатов во избежание ошибок с кнопками в группах
    telegram_application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))

    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()

    logger.info("==> Telegram бот запущен через run_polling()")
    
    try:
        bot_loop = asyncio.get_running_loop()
    except RuntimeError:
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)

    telegram_application.run_polling()


if __name__ == "__main__":
    main()
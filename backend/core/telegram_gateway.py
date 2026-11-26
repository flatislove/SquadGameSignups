import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class TelegramGateway:
    def __init__(self):
        self._bot = None

    def set_bot(self, bot):
        self._bot = bot

    async def send_game_announcement(
        self,
        chat_id: int,
        game_id: str,
        game_data: dict,
        bot_username: str
    ):
        if not self._bot:
            logger.error("TelegramGateway bot instance not set.")
            return None

        text = (
            f"🏐 **Волейбольный матч!**\n\n"
            f"📅 **Дата:** {game_data.get('date', 'Уточняется')}\n"
            f"⏰ **Время:** {game_data.get('time_start', '')} - {game_data.get('time_end', '')}\n"
            f"📍 **Площадка:** {game_data.get('loc_name', 'Уточняется')}\n"
            f"🗺 [Ссылка на карту]({game_data.get('loc_link', '#')})\n"
            f"💰 **Стоимость:** {game_data.get('cost', 'Бесплатно')}\n"
            f"👥 **Максимум игроков:** {game_data.get('max_players', 'Не указано')}\n"
            f"👤 **Организатор:** {game_data.get('org_name', '')} ({game_data.get('org_phone', '')})"
        )

        web_app_url = f"https://t.me/{bot_username}?startapp=game_{game_id}"
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🏐 Управлять записью",
                    url=web_app_url
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            msg = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            logger.info(f"Successfully sent announcement for game {game_id} to chat {chat_id}, message_id: {msg.message_id}")
            return msg.message_id
        except TelegramError as te:
            logger.error(f"Telegram error sending announcement to chat {chat_id}: {te}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending announcement to chat {chat_id}: {e}")
            return None

telegram_gateway = TelegramGateway()

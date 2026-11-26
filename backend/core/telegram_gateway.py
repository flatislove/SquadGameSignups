from html import escape
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def _format_hm(raw_time: str) -> str:
    val = str(raw_time or "").strip()
    if not val:
        return ""
    parts = val.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return val


def build_announcement_text(
    game_data: dict,
    main_count: int = 0,
    max_players: int | None = None,
    reserve_count: int = 0,
) -> str:
    date_str = str(game_data.get("date") or "Уточняется").strip()
    time_start = _format_hm(str(game_data.get("time_start") or ""))
    time_end = _format_hm(str(game_data.get("time_end") or ""))

    if time_start and time_end:
        time_part = f" ({time_start} - {time_end})"
    elif time_start:
        time_part = f" ({time_start})"
    else:
        time_part = ""

    date_line = f"📅 {escape(f'{date_str}{time_part}')}"

    loc_name = escape(str(game_data.get("loc_name") or "Уточняется").strip())
    loc_link = str(game_data.get("loc_link") or "").strip()
    if loc_link.startswith(("http://", "https://")):
        location_line = f'📍 <a href="{escape(loc_link, quote=True)}">{loc_name}</a>'
    else:
        location_line = f"📍 {loc_name}"

    cost = escape(str(game_data.get("cost") or "Бесплатно").strip())
    org_name = str(game_data.get("org_name") or "").strip()
    org_phone = str(game_data.get("org_phone") or "").strip()
    org_part = f"{org_name} ({org_phone})" if org_phone else org_name

    limit = max_players if max_players is not None else (game_data.get("max_players") or 0)
    roster_line = escape(f"{main_count}/{limit} Список; {reserve_count} резерв")

    lines = [
        "🏐 Volleyball",
        "",
        date_line,
        location_line,
        f"💰 {cost}",
    ]
    if org_part:
        lines.append(f"👤 {escape(org_part)}")
    lines.extend([
        "",
        roster_line,
    ])
    return "\n".join(lines)


def _build_signup_button(web_app_url: str) -> InlineKeyboardButton:
    try:
        return InlineKeyboardButton(
            text="Запись",
            url=web_app_url,
            api_kwargs={"style": "success"},
        )
    except TypeError:
        return InlineKeyboardButton(
            text="Запись",
            url=web_app_url,
        )


class TelegramGateway:
    def __init__(self):
        self._bot = None

    def set_bot(self, bot):
        self._bot = bot

    def build_markup(self, game_id: str, bot_username: str) -> InlineKeyboardMarkup:
        web_app_url = f"https://t.me/{bot_username}?startapp=game_{game_id}"
        return InlineKeyboardMarkup([[_build_signup_button(web_app_url)]])

    async def send_game_announcement(
        self,
        chat_id: int,
        game_id: str,
        game_data: dict,
        bot_username: str,
        main_count: int = 0,
        reserve_count: int = 0,
    ):
        if not self._bot:
            logger.error("TelegramGateway bot instance not set.")
            return None

        text = build_announcement_text(
            game_data=game_data,
            main_count=main_count,
            max_players=game_data.get("max_players"),
            reserve_count=reserve_count,
        )
        reply_markup = self.build_markup(game_id=game_id, bot_username=bot_username)

        try:
            msg = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(
                f"Successfully sent announcement for game {game_id} to chat {chat_id}, message_id: {msg.message_id}"
            )
            return msg.message_id
        except TelegramError as te:
            logger.error(f"Telegram error sending announcement to chat {chat_id}: {te}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending announcement to chat {chat_id}: {e}")
            return None

    async def update_game_announcement(
        self,
        chat_id: int,
        message_id: int,
        game_id: str,
        game_data: dict,
        bot_username: str,
        main_count: int,
        reserve_count: int,
    ) -> bool:
        if not self._bot or not chat_id or not message_id:
            return False

        text = build_announcement_text(
            game_data=game_data,
            main_count=main_count,
            max_players=game_data.get("max_players"),
            reserve_count=reserve_count,
        )
        reply_markup = self.build_markup(game_id=game_id, bot_username=bot_username)

        try:
            await self._bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except TelegramError as te:
            if "message is not modified" in str(te).lower():
                return True
            logger.warning(
                f"Failed to edit announcement message {message_id} in chat {chat_id}: {te}"
            )
            return False
        except Exception as e:
            logger.warning(
                f"Unexpected error editing announcement message {message_id} in chat {chat_id}: {e}"
            )
            return False


telegram_gateway = TelegramGateway()
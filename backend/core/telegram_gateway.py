from datetime import datetime
from html import escape
import logging
from urllib.parse import quote
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

DEFAULT_WEBAPP_BASE_URL = "https://flatislove.github.io/SquadGameSignups"

_RU_WEEKDAYS = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}


def _format_hm(raw_time: str) -> str:
    val = str(raw_time or "").strip()
    if not val:
        return ""
    parts = val.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return val


def _format_date_with_weekday(raw_date: str) -> str:
    date_str = str(raw_date or "").strip()
    if not date_str:
        return "Уточняется"
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        weekday_ru = _RU_WEEKDAYS.get(dt.weekday())
        if weekday_ru:
            return f"{date_str}, {weekday_ru}"
    except ValueError:
        pass
    return date_str


def build_announcement_text(
    game_data: dict,
    main_count: int = 0,
    max_players: int | None = None,
    reserve_count: int = 0,
) -> str:
    date_label = _format_date_with_weekday(str(game_data.get("date") or ""))
    time_start = _format_hm(str(game_data.get("time_start") or ""))
    time_end = _format_hm(str(game_data.get("time_end") or ""))

    if time_start and time_end:
        time_label = f"{time_start} - {time_end}"
    elif time_start:
        time_label = time_start
    else:
        time_label = ""

    date_line = f"📅 {escape(date_label)}"

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
    ]
    if time_label:
        lines.append(f"🕒 {escape(time_label)}")
    lines.extend([
        location_line,
        f"💰 {cost}",
    ])
    if org_part:
        lines.append(f"👤 {escape(org_part)}")
    lines.extend([
        "",
        roster_line,
    ])
    return "\n".join(lines)


def build_signup_page_url(
    game_id: str,
    base_url: str = DEFAULT_WEBAPP_BASE_URL,
) -> str:
    clean_base = str(base_url or DEFAULT_WEBAPP_BASE_URL).strip().rstrip("/")
    clean_game_id = quote(str(game_id or "").strip(), safe="")
    return f"{clean_base}/signup.html?game_id={clean_game_id}"


def build_signup_deep_link(game_id: str, bot_username: str) -> str:
    clean_username = str(bot_username or "").strip().lstrip("@")
    clean_game_id = str(game_id or "").strip()
    return f"https://t.me/{clean_username}?startapp=game_{clean_game_id}"


def _build_signup_button(signup_url: str, use_web_app: bool = False) -> InlineKeyboardButton:
    button_kwargs = {"text": "Запись"}
    if use_web_app:
        button_kwargs["web_app"] = WebAppInfo(url=signup_url)
    else:
        button_kwargs["url"] = signup_url

    try:
        return InlineKeyboardButton(**button_kwargs, api_kwargs={"style": "success"})
    except TypeError:
        return InlineKeyboardButton(**button_kwargs)


class TelegramGateway:
    def __init__(self, webapp_base_url: str = DEFAULT_WEBAPP_BASE_URL, use_web_app: bool = False):
        self._bot = None
        self._webapp_base_url = webapp_base_url
        self._use_web_app = use_web_app

    def set_bot(self, bot):
        self._bot = bot

    def build_markup(self, game_id: str, bot_username: str | None = None) -> InlineKeyboardMarkup:
        signup_url = build_signup_page_url(
            game_id=game_id,
            base_url=self._webapp_base_url,
        )
        return InlineKeyboardMarkup(
            [[_build_signup_button(signup_url, use_web_app=self._use_web_app)]]
        )

    async def send_game_announcement(
        self,
        chat_id: int,
        game_id: str,
        game_data: dict,
        bot_username: str = "",
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
        bot_username: str = "",
        main_count: int = 0,
        reserve_count: int = 0,
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
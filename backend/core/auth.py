import hmac
import hashlib
import time
import json
import logging
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException, status
from backend.core.config import settings

logger = logging.getLogger(__name__)

# TTL cache for chat member admin status: {(chat_id, user_id): (is_admin, timestamp)}
_admin_cache: dict[tuple[int, int], tuple[bool, float]] = {}
CACHE_TTL = 120  # 2 minutes


def is_superuser(user_id: int | None) -> bool:
    """Checks if the user is a superuser based on config."""
    if user_id is None:
        return False
    return int(user_id) in settings.superuser_ids


def verify_telegram_init_data(init_data: str) -> dict:
    """
    Validates Telegram WebApp initData according to Telegram official docs:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram initData header",
        )

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid initData: missing hash",
            )

        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > 86400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="initData expired",
            )

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        secret_key = hmac.new(
            key=b"WebAppData",
            msg=settings.BOT_TOKEN.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="initData signature verification failed",
            )

        user_str = parsed.get("user")
        if not user_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="initData missing user object",
            )

        return json.loads(user_str)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating initData: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData format",
        )


async def get_current_user(x_telegram_init_data: str = Header(None)) -> dict:
    """FastAPI Dependency to extract and validate current user from X-Telegram-Init-Data header."""
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Telegram-Init-Data header is required",
        )
    return verify_telegram_init_data(x_telegram_init_data)


async def verify_chat_admin(bot, chat_id: int, user_id: int) -> bool:
    """Checks if user is administrator or creator in the given chat, with TTL cache."""
    if is_superuser(user_id):
        return True

    cache_key = (int(chat_id), int(user_id))
    now = time.monotonic()

    cached = _admin_cache.get(cache_key)
    if cached is not None:
        is_admin, timestamp = cached
        if now - timestamp < CACHE_TTL:
            return is_admin

    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=int(user_id))
        is_admin = member.status in ("creator", "administrator")
        _admin_cache[cache_key] = (is_admin, now)
        return is_admin
    except Exception as e:
        logger.error(f"Failed to check chat member status for user {user_id} in chat {chat_id}: {e}")
        return False
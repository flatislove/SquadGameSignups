from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from backend.core.auth import get_current_user, verify_chat_admin
from backend.core.db import get_db
from backend.core.telegram_gateway import telegram_gateway
import logging

router = APIRouter(prefix="/api/signups", tags=["signups"])
logger = logging.getLogger(__name__)

# Простой кэш имен из Telegram: {user_id: display_name}
_tg_names_cache: dict[int, str] = {}


class SignupSchema(BaseModel):
    game_id: str


class AdminAddSignupSchema(BaseModel):
    game_id: str
    user_id: int | None = None
    user_name: str
    user_phone: str | None = None
    is_paid: bool = False


class TogglePaySchema(BaseModel):
    is_paid: bool


def _format_tg_user_name(chat_or_user) -> str | None:
    if not chat_or_user:
        return None
    full_name = " ".join(
        p for p in [getattr(chat_or_user, "first_name", None), getattr(chat_or_user, "last_name", None)] if p
    ).strip()
    if full_name:
        return full_name
    username = getattr(chat_or_user, "username", None)
    if username:
        return f"@{username}"
    title = getattr(chat_or_user, "title", None)
    if title:
        return title
    return None


async def _resolve_telegram_name(user_id: int) -> str | None:
    if user_id in _tg_names_cache:
        return _tg_names_cache[user_id]
    bot = getattr(telegram_gateway, "_bot", None)
    if not bot:
        return None
    try:
        tg_chat = await bot.get_chat(user_id)
        name = _format_tg_user_name(tg_chat)
        if name:
            _tg_names_cache[user_id] = name
            return name
    except Exception as e:
        logger.debug(f"Could not fetch Telegram name for user_id={user_id}: {e}")
    return None


async def _enrich_signups(db, game_id: str, signups: list[dict]) -> list[dict]:
    missing_user_ids = [
        s.get("user_id")
        for s in signups
        if not s.get("user_name") and s.get("user_id") is not None
    ]
    users_map: dict[int, str] = {}

    if missing_user_ids:
        try:
            users_res = (
                db.table("users")
                .select("id, username, first_name, last_name")
                .in_("id", list(set(missing_user_ids)))
                .execute()
            )
            for u in users_res.data or []:
                uid = u.get("id")
                full_name = " ".join(
                    p for p in [u.get("first_name"), u.get("last_name")] if p
                ).strip()
                resolved = full_name or (f"@{u['username']}" if u.get("username") else None)
                if uid is not None and resolved:
                    users_map[int(uid)] = resolved
        except Exception as e:
            logger.warning(f"Failed to load users for game {game_id}: {e}")

    for s in signups:
        uid = s.get("user_id")
        if not s.get("user_name"):
            name = users_map.get(int(uid)) if uid is not None else None
            if not name and uid is not None:
                name = await _resolve_telegram_name(int(uid))
            s["user_name"] = name or "Участник"
        if "is_paid" not in s:
            s["is_paid"] = bool(s.get("paid", False))

    return signups


async def _check_game_admin(game: dict, user_id: int | None) -> bool:
    chat_id = game.get("group_id") or game.get("chat_id")
    bot = getattr(telegram_gateway, "_bot", None)
    if not chat_id or user_id is None or not bot:
        return False
    try:
        return bool(await verify_chat_admin(bot, int(chat_id), int(user_id)))
    except Exception as e:
        logger.warning(f"Failed to check admin rights for user {user_id} in chat {chat_id}: {e}")
        return False


@router.get("/status")
async def get_signup_status(game_id: str, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        game_res = db.table("games").select("*").eq("id", game_id).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]
        max_players = game.get("max_players") or 0

        signups_res = (
            db.table("signups")
            .select("*")
            .eq("game_id", game_id)
            .order("created_at", desc=False)
            .execute()
        )
        signups = await _enrich_signups(db, game_id, signups_res.data or [])

        main_list = [s for s in signups if s.get("status") == "main"]
        reserve_list = [s for s in signups if s.get("status") == "reserve"]

        user_signup = next((s for s in signups if s.get("user_id") == user_id), None)

        status_val = "not_registered"
        message = f"Свободных мест: {max(0, max_players - len(main_list))}"

        if user_signup:
            if user_signup.get("status") == "main":
                status_val = "main"
                message = "✅ Вы записаны в ОСНОВНОЙ состав!"
            else:
                status_val = "reserve"
                message = "⚠️ Мест нет, вы находитесь в РЕЗЕРВЕ."

        is_admin = await _check_game_admin(game, user_id)

        return {
            "status": status_val,
            "message": message,
            "main_count": len(main_list),
            "reserve_count": len(reserve_list),
            "max_players": max_players,
            "game": game,
            "signups": signups,
            "is_admin": is_admin,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting signup status for game {game_id}, user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("")
async def cancel_signup(game_id: str, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        db.table("signups").delete().eq("game_id", game_id).eq("user_id", user_id).execute()

        game_res = db.table("games").select("max_players").eq("id", game_id).execute()
        if game_res.data:
            max_players = game_res.data[0].get("max_players") or 0
            signups_res = (
                db.table("signups")
                .select("*")
                .eq("game_id", game_id)
                .order("created_at", desc=False)
                .execute()
            )
            all_signups = signups_res.data or []
            main_list = [s for s in all_signups if s.get("status") == "main"]
            reserve_list = [s for s in all_signups if s.get("status") == "reserve"]

            if len(main_list) < max_players and reserve_list:
                first_reserve = reserve_list[0]
                db.table("signups").update({"status": "main"}).eq("id", first_reserve["id"]).execute()

        return {"success": True}
    except Exception as e:
        logger.error(f"Error cancelling signup for user {user_id} in game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
async def signup_user(payload: SignupSchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    game_id = payload.game_id
    db = get_db()

    try:
        existing = (
            db.table("signups")
            .select("*")
            .eq("game_id", game_id)
            .eq("user_id", user_id)
            .execute()
        )
        if existing.data:
            return {"success": True, "status": existing.data[0]["status"]}

        game_res = db.table("games").select("max_players").eq("id", game_id).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        max_players = game_res.data[0].get("max_players") or 0

        main_res = (
            db.table("signups")
            .select("id", count="exact")
            .eq("game_id", game_id)
            .eq("status", "main")
            .execute()
        )
        main_count = len(main_res.data) if main_res.data else 0
        signup_status = "main" if main_count < max_players else "reserve"

        tg_name = _format_tg_user_name(type("TgUser", (), user)())
        if user_id is not None and tg_name:
            _tg_names_cache[int(user_id)] = tg_name

        row = {
            "game_id": game_id,
            "user_id": user_id,
            "status": signup_status,
            "is_paid": False,
        }
        try:
            if tg_name:
                row["user_name"] = tg_name
            db.table("signups").insert(row).execute()
        except Exception:
            row.pop("user_name", None)
            db.table("signups").insert(row).execute()

        return {"success": True, "status": signup_status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error signing up user {user_id} for game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/admin-add")
async def admin_add_signup(payload: AdminAddSignupSchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        game_res = db.table("games").select("*").eq("id", payload.game_id).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]

        if not await _check_game_admin(game, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        max_players = game.get("max_players") or 0
        signups_res = (
            db.table("signups")
            .select("id, status")
            .eq("game_id", payload.game_id)
            .execute()
        )
        existing_signups = signups_res.data or []
        main_count = sum(1 for s in existing_signups if s.get("status") == "main")
        signup_status = "main" if main_count < max_players else "reserve"

        clean_name = (payload.user_name or "").strip() or "Участник"
        synthetic_user_id = payload.user_id if payload.user_id is not None else -int(__import__("time").time() * 1000)

        insert_data = {
            "game_id": payload.game_id,
            "user_id": synthetic_user_id,
            "user_name": clean_name,
            "status": signup_status,
            "is_paid": bool(payload.is_paid),
        }
        try:
            db.table("signups").insert(insert_data).execute()
        except Exception:
            insert_data.pop("user_name", None)
            db.table("signups").insert(insert_data).execute()

        return {"success": True, "status": signup_status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin_add_signup for game {payload.game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{signup_id}/pay")
async def toggle_signup_payment(signup_id: str, payload: TogglePaySchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        s_res = db.table("signups").select("*").eq("id", signup_id).execute()
        if not s_res.data:
            raise HTTPException(status_code=404, detail="Signup not found")
        signup = s_res.data[0]

        game_res = db.table("games").select("*").eq("id", signup["game_id"]).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")

        if not await _check_game_admin(game_res.data[0], user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        db.table("signups").update({"is_paid": bool(payload.is_paid)}).eq("id", signup_id).execute()
        return {"success": True, "is_paid": bool(payload.is_paid)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling payment for signup {signup_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{signup_id}/admin-remove")
async def admin_remove_signup(signup_id: str, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        s_res = db.table("signups").select("*").eq("id", signup_id).execute()
        if not s_res.data:
            raise HTTPException(status_code=404, detail="Signup not found")
        signup = s_res.data[0]
        game_id = signup["game_id"]

        game_res = db.table("games").select("*").eq("id", game_id).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]

        if not await _check_game_admin(game, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        db.table("signups").delete().eq("id", signup_id).execute()

        max_players = game.get("max_players") or 0
        all_res = (
            db.table("signups")
            .select("*")
            .eq("game_id", game_id)
            .order("created_at", desc=False)
            .execute()
        )
        all_signups = all_res.data or []
        main_list = [s for s in all_signups if s.get("status") == "main"]
        reserve_list = [s for s in all_signups if s.get("status") == "reserve"]

        if len(main_list) < max_players and reserve_list:
            db.table("signups").update({"status": "main"}).eq("id", reserve_list[0]["id"]).execute()

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing signup {signup_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
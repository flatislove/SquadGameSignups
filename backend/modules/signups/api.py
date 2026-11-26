from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.core.auth import get_current_user, verify_chat_admin
from backend.core.db import get_db
import logging

router = APIRouter(prefix="/api/signups", tags=["signups"])
logger = logging.getLogger(__name__)


class SignupSchema(BaseModel):
    game_id: str


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
        signups = signups_res.data or []

        # Подставляем user_name из таблицы users, если в signups его нет
        missing_user_ids = [
            s.get("user_id")
            for s in signups
            if not s.get("user_name") and s.get("user_id") is not None
        ]
        users_map = {}
        if missing_user_ids:
            try:
                users_res = (
                    db.table("users")
                    .select("id, username, first_name, last_name")
                    .in_("id", list(set(missing_user_ids)))
                    .execute()
                )
                for u in users_res.data or []:
                    full_name = " ".join(
                        p for p in [u.get("first_name"), u.get("last_name")] if p
                    ).strip()
                    users_map[u.get("id")] = (
                        full_name
                        or (f"@{u['username']}" if u.get("username") else None)
                        or f"Игрок {u.get('id')}"
                    )
            except Exception as e:
                logger.warning(f"Failed to enrich signup user names for game {game_id}: {e}")

        for s in signups:
            if not s.get("user_name"):
                uid = s.get("user_id")
                s["user_name"] = users_map.get(uid) or f"Игрок {uid}"
            if "is_paid" not in s:
                s["is_paid"] = bool(s.get("paid", False))

        main_list = [s for s in signups if s.get("status") == "main"]
        reserve_list = [s for s in signups if s.get("status") == "reserve"]

        user_signup = next((s for s in signups if s.get("user_id") == user_id), None)

        status = "not_registered"
        message = f"Свободных мест: {max(0, max_players - len(main_list))}"

        if user_signup:
            if user_signup.get("status") == "main":
                status = "main"
                message = "✅ Вы записаны в ОСНОВНОЙ состав!"
            else:
                status = "reserve"
                message = "⚠️ Мест нет, вы находитесь в РЕЗЕРВЕ."

        is_admin = False
        chat_id = game.get("chat_id") or game.get("group_id")
        if chat_id and user_id is not None:
            try:
                is_admin = bool(await verify_chat_admin(chat_id=chat_id, user_id=user_id))
            except Exception as e:
                logger.warning(f"Failed to verify admin status for user {user_id} in chat {chat_id}: {e}")
                is_admin = False

        return {
            "status": status,
            "message": message,
            "main_count": len(main_list),
            "reserve_count": len(reserve_list),
            "max_players": max_players,
            "game": game,
            "signups": signups,
            "is_admin": is_admin,
        }

    except HTTPException as he:
        raise he
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

        db.table("signups").insert({
            "game_id": game_id,
            "user_id": user_id,
            "status": signup_status,
        }).execute()

        return {"success": True, "status": signup_status}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error signing up user {user_id} for game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
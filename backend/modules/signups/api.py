from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.core.auth import get_current_user
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
        # Get game info
        game_res = db.table("games").select("*").eq("id", game_id).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]
        max_players = game["max_players"]

        # Get all signups for this game ordered by creation time
        signups_res = db.table("signups").select("*").eq("game_id", game_id).order("created_at", desc=False).execute()
        signups = signups_res.data or []

        main_list = [s for s in signups if s["status"] == "main"]
        reserve_list = [s for s in signups if s["status"] == "reserve"]

        user_signup = next((s for s in signups if s["user_id"] == user_id), None)
        
        status = "not_registered"
        message = f"Свободных мест: {max(0, max_players - len(main_list))}"

        if user_signup:
            if user_signup["status"] == "main":
                status = "main"
                message = "✅ Вы записаны в ОСНОВНОЙ состав!"
            else:
                status = "reserve"
                message = "⚠️ Мест нет, вы находитесь в РЕЗЕРВЕ."

        return {
            "status": status,
            "message": message,
            "main_count": len(main_list),
            "reserve_count": len(reserve_list),
            "max_players": max_players
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting signup status for game {game_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("")
async def signup_user(payload: SignupSchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    game_id = payload.game_id
    db = get_db()

    try:
        # Check if already signed up
        existing = db.table("signups").select("*").eq("game_id", game_id).eq("user_id", user_id).execute()
        if existing.data:
            return {"success": True, "status": existing.data[0]["status"]}

        # Get game max players
        game_res = db.table("games").select("max_players").eq("id", game_id).execute()
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        max_players = game_res.data[0]["max_players"]

        # Count main signups
        main_res = db.table("signups").select("id", count="exact").eq("game_id", game_id).eq("status", "main").execute()
        main_count = len(main_res.data) if main_res.data else 0

        signup_status = "main" if main_count < max_players else "reserve"

        db.table("signups").insert({
            "game_id": game_id,
            "user_id": user_id,
            "status": signup_status
        }).execute()

        return {"success": True, "status": signup_status}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error signing up user {user_id} for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

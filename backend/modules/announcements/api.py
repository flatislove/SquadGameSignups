from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from backend.core.auth import get_current_user, verify_chat_admin
from backend.core.db import get_db
from backend.core.telegram_gateway import telegram_gateway
from backend.core.config import settings
import logging

router = APIRouter(prefix="/api/games", tags=["games"])
logger = logging.getLogger(__name__)

class GameCreateSchema(BaseModel):
    chat_id: int
    date: str
    time: str # time_start
    end_time: str
    publish_time: str = "now"
    venue_id: str | None = None
    loc_name: str | None = None
    loc_link: str | None = None
    cost: str
    max_players: int = 12
    name: str # org_name
    phone: str # org_phone

@router.post("/create")
async def create_game(payload: GameCreateSchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    
    if not telegram_gateway._bot:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")

    # Verify user is admin in target chat
    is_admin = await verify_chat_admin(telegram_gateway._bot, payload.chat_id, user_id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an administrator in this group"
        )

    db = get_db()
    
    try:
        loc_name = payload.loc_name or ""
        loc_link = payload.loc_link or ""
        venue_id = payload.venue_id

        if venue_id:
            venue_res = db.table("venues").select("*").eq("id", venue_id).execute()
            if venue_res.data:
                v = venue_res.data[0]
                loc_name = v["name"]
                loc_link = v["map_url"]

        game_insert = {
            "group_id": payload.chat_id,
            "date": payload.date,
            "time_start": payload.time,
            "time_end": payload.end_time,
            "venue_id": venue_id,
            "loc_name": loc_name,
            "loc_link": str(loc_link),
            "cost": payload.cost,
            "max_players": payload.max_players,
            "org_name": payload.name,
            "org_phone": payload.phone,
            "status": "active",
            "publish_time": payload.publish_time
        }

        res = db.table("games").insert(game_insert).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to save game in database")
        
        created_game = res.data[0]
        game_id = created_game["id"]

        # If publish_time is 'now', send immediately
        if payload.publish_time == "now":
            msg_id = await telegram_gateway.send_game_announcement(
                chat_id=payload.chat_id,
                game_id=game_id,
                game_data=game_insert,
                bot_username=settings.BOT_USERNAME
            )
            if msg_id:
                db.table("games").update({"message_id": msg_id}).eq("id", game_id).execute()
        else:
            pass

        return {"success": True, "game_id": game_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{game_id}")
async def get_game(game_id: str):
    db = get_db()
    try:
        res = db.table("games").select("*").eq("id", game_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        return res.data[0]
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching game {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/latest")
async def get_latest_game():
    db = get_db()
    try:
        res = db.table("games").select("*").eq("status", "active").order("created_at", desc=True).limit(1).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="No active games found")
        return res.data[0]
    except Exception as e:
        logger.error(f"Error fetching latest game: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


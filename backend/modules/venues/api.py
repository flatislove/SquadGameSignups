import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.auth import get_current_user
from backend.core.db import get_db

from backend.core.telegram_gateway import telegram_gateway
from backend.core.auth import verify_chat_admin

router = APIRouter(prefix="/api/venues", tags=["venues"])
logger = logging.getLogger(__name__)


class VenueCreateSchema(BaseModel):
    chat_id: int
    name: str = Field(..., min_length=1)
    map_url: str = Field(..., min_length=1)


class VenueUpdateSchema(BaseModel):
    name: str | None = None
    map_url: str | None = None
    is_active: bool | None = None
    chat_id: int | None = None


async def _ensure_chat_admin(chat_id: int, user_id: int | None) -> None:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID is missing",
        )
    if not getattr(telegram_gateway, "_bot", None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram bot not initialized",
        )
    # Если у verify_chat_admin сигнатура (bot, user_id, chat_id), замени на:
    # is_admin = await verify_chat_admin(telegram_gateway._bot, user_id, chat_id)
    is_admin = await verify_chat_admin(telegram_gateway._bot, chat_id, user_id)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an administrator in this group",
        )


@router.get("")
async def get_venues(chat_id: int | None = None, user: dict = Depends(get_current_user)):
    """Returns active venues list."""
    db = get_db()
    try:
        query = db.table("venues").select("*").eq("is_active", True)
        if chat_id is not None:
            query = query.eq("chat_id", chat_id)
        res = query.order("name").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching venues: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
async def create_venue(payload: VenueCreateSchema, user: dict = Depends(get_current_user)):
    """Create a new venue."""
    user_id = user.get("id")
    await _ensure_chat_admin(payload.chat_id, user_id)

    db = get_db()
    try:
        insert_data = {
            "chat_id": payload.chat_id,
            "name": payload.name.strip(),
            "map_url": payload.map_url.strip(),
            "is_active": True,
        }
        res = db.table("venues").insert(insert_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create venue")
        return {"success": True, "venue": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating venue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{venue_id}")
async def update_venue(
    venue_id: str,
    payload: VenueUpdateSchema,
    user: dict = Depends(get_current_user),
):
    """Update venue details."""
    user_id = user.get("id")
    db = get_db()
    try:
        v_res = db.table("venues").select("chat_id").eq("id", venue_id).execute()
        if not v_res.data:
            raise HTTPException(status_code=404, detail="Venue not found")

        venue_chat_id = v_res.data[0].get("chat_id")
        target_chat_id = payload.chat_id if payload.chat_id is not None else venue_chat_id

        if target_chat_id is not None:
            await _ensure_chat_admin(target_chat_id, user_id)

        update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        res = db.table("venues").update(update_data).eq("id", venue_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Venue not found")
        return {"success": True, "venue": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating venue {venue_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{venue_id}")
async def delete_venue(venue_id: str, user: dict = Depends(get_current_user)):
    """Soft delete / deactivate venue."""
    user_id = user.get("id")
    db = get_db()
    try:
        v_res = db.table("venues").select("chat_id").eq("id", venue_id).execute()
        if not v_res.data:
            raise HTTPException(status_code=404, detail="Venue not found")

        venue_chat_id = v_res.data[0].get("chat_id")
        if venue_chat_id is not None:
            await _ensure_chat_admin(venue_chat_id, user_id)

        res = db.table("venues").update({"is_active": False}).eq("id", venue_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Venue not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting venue {venue_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from backend.core.auth import get_current_user
from backend.core.db import get_db
import logging

router = APIRouter(prefix="/api/venues", tags=["venues"])
logger = logging.getLogger(__name__)

class VenueCreateSchema(BaseModel):
    name: str
    map_url: str

class VenueUpdateSchema(BaseModel):
    name: str | None = None
    map_url: str | None = None
    is_active: bool | None = None

@router.get("")
async def get_venues(user: dict = Depends(get_current_user)):
    """Returns active venues list."""
    db = get_db()
    try:
        res = db.table("venues").select("*").eq("is_active", True).order("name").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching venues: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("")
async def create_venue(payload: VenueCreateSchema, user: dict = Depends(get_current_user)):
    """Create a new venue."""
    db = get_db()
    try:
        insert_data = {
            "name": payload.name,
            "map_url": str(payload.map_url),
            "is_active": True
        }
        res = db.table("venues").insert(insert_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create venue")
        return {"success": True, "venue": res.data[0]}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating venue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{venue_id}")
async def update_venue(venue_id: str, payload: VenueUpdateSchema, user: dict = Depends(get_current_user)):
    """Update venue details."""
    db = get_db()
    try:
        update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        res = db.table("venues").update(update_data).eq("id", venue_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Venue not found")
        return {"success": True, "venue": res.data[0]}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating venue {venue_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{venue_id}")
async def delete_venue(venue_id: str, user: dict = Depends(get_current_user)):
    """Soft delete / deactivate venue."""
    db = get_db()
    try:
        res = db.table("venues").update({"is_active": False}).eq("id", venue_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Venue not found")
        return {"success": True}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting venue {venue_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

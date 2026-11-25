from fastapi import APIRouter, Depends, HTTPException
from backend.core.auth import get_current_user, verify_chat_admin
from backend.core.db import get_db
import logging

router = APIRouter(prefix="/api/groups", tags=["groups"])
logger = logging.getLogger(__name__)

@router.get("/admin-chats")
async def get_admin_chats(user: dict = Depends(get_current_user)):
    """
    Returns list of groups where current user is admin or creator,
    and bot is active.
    """
    db = get_db()
    user_id = user.get("id")
    
    try:
        res = db.table("groups").select("*").eq("is_active", True).execute()
        groups = res.data or []
        
        admin_chats = []
        # We need bot instance from telegram application or gateway
        from backend.core.telegram_gateway import telegram_gateway
        
        if not telegram_gateway._bot:
            # Fallback if bot not ready
            return []

        for group in groups:
            group_id = group["group_id"]
            try:
                member = await telegram_gateway._bot.get_chat_member(chat_id=group_id, user_id=user_id)
                if member.status in ["creator", "administrator"]:
                    admin_chats.append({
                        "id": group_id,
                        "title": group["title"]
                    })
            except Exception as e:
                logger.debug(f"User {user_id} is not admin in group {group_id}: {e}")

        return admin_chats
    except Exception as e:
        logger.error(f"Error fetching admin chats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

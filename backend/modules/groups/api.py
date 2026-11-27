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
    
    logger.info(f"Fetching admin chats for user_id={user_id}")
    
    try:
        res = db.table("groups").select("*").eq("is_active", True).execute()
        groups = res.data or []
        logger.info(f"Found {len(groups)} total active groups in DB")
        
        admin_chats = []
        from backend.core.telegram_gateway import telegram_gateway
        
        if not telegram_gateway._bot:
            logger.warning("Telegram bot instance is not available for chat member check")
            return []

        for group in groups:
            chat_id = group["chat_id"]
            try:
                member = await telegram_gateway._bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                logger.info(f"User {user_id} status in chat {chat_id}: {member.status}")
                if member.status in ["creator", "administrator"]:
                    admin_chats.append({
                        "id": chat_id,
                        "title": group["title"]
                    })
            except Exception as e:
                logger.warning(f"Failed to check admin status for user {user_id} in group {chat_id}: {e}")
        
        logger.info(f"Returning {len(admin_chats)} admin chats for user_id={user_id}")
        return admin_chats
    except Exception as e:
        logger.error(f"Critical error fetching admin chats for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

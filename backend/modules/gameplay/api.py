from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any
from backend.core.auth import get_current_user, verify_chat_admin, is_superuser
from backend.core.db import get_db
from backend.core.telegram_gateway import telegram_gateway
import asyncio
import logging

router = APIRouter(prefix="/api/gameplay", tags=["gameplay"])
logger = logging.getLogger(__name__)

async def _db(fn):
    return await asyncio.to_thread(fn)

async def _check_game_admin_by_id(db, game_id: str, user_id: int | None) -> bool:
    if is_superuser(user_id):
        return True
    game_res = await _db(lambda: db.table("games").select("group_id, chat_id").eq("id", game_id).execute())
    if not game_res.data:
        return False
    game = game_res.data[0]
    chat_id = game.get("group_id") or game.get("chat_id")
    bot = getattr(telegram_gateway, "_bot", None)
    if not chat_id or user_id is None or not bot:
        return False
    try:
        return bool(await verify_chat_admin(bot, int(chat_id), int(user_id)))
    except Exception as e:
        logger.warning(f"Failed to check admin rights for user {user_id} in chat {chat_id}: {e}")
        return False

class TeamCreateOrUpdateSchema(BaseModel):
    game_id: str
    name: str
    color: str | None = None

class LineupAssignSchema(BaseModel):
    game_id: str
    team_id: str
    player_id: str

class MatchCreateSchema(BaseModel):
    game_id: str
    left_team_id: str
    right_team_id: str

class MatchScoreUpdateSchema(BaseModel):
    left_score: int
    right_score: int
    status: str | None = None

class ActionLogSchema(BaseModel):
    game_id: str
    match_id: str | None = None
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)

class CommunityActionSchema(BaseModel):
    chat_id: int
    title: str
    description: str | None = None
    is_active: bool = True


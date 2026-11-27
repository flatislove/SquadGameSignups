from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any
from backend.core.auth import get_current_user, verify_chat_admin, is_superuser
from backend.core.db import get_db
from backend.core.telegram_gateway import telegram_gateway
import asyncio
import logging

router = APIRouter(prefix="/api/match", tags=["match"])
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

async def _check_chat_admin(db, chat_id: int, user_id: int | None) -> bool:
    if is_superuser(user_id):
        return True
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

class LineupReplaceSchema(BaseModel):
    game_id: str
    old_player_id: str
    new_player_id: str
    team_id: str | None = None

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
    actor_id: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

class CommunityActionSchema(BaseModel):
    chat_id: int
    title: str
    description: str | None = None
    is_active: bool = True



@router.get("/{game_id}/state")
async def get_match_state(game_id: str, user: dict = Depends(get_current_user)):
    """
    GET /api/match/{game_id}/state — returns teams (from game_teams), lineups (from game_lineups),
    matches (from game_matches), actions (from community_actions by chat_id),
    and last_action (the last active record from game_action_logs).
    """
    db = get_db()
    try:
        game_res = await _db(lambda: db.table("games").select("*").eq("id", game_id).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]
        chat_id = game.get("group_id") or game.get("chat_id")

        teams_res, lineups_res, matches_res, actions_res, logs_res = await asyncio.gather(
            _db(lambda: db.table("game_teams").select("*").eq("game_id", game_id).execute()),
            _db(lambda: db.table("game_lineups").select("*").eq("game_id", game_id).execute()),
            _db(lambda: db.table("game_matches").select("*").eq("game_id", game_id).execute()),
            _db(lambda: db.table("community_actions").select("*").eq("chat_id", chat_id).execute() if chat_id else type('obj', (), {'data': []})()),
            _db(lambda: db.table("game_action_logs").select("*").eq("game_id", game_id).order("created_at", desc=True).limit(1).execute()),
        )

        last_action = logs_res.data[0] if logs_res.data else None

        return {
            "teams": teams_res.data or [],
            "lineups": lineups_res.data or [],
            "matches": matches_res.data or [],
            "actions": actions_res.data or [],
            "last_action": last_action
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching match state for game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/actions")
async def get_match_actions(chat_id: int, user: dict = Depends(get_current_user)):
    """
    GET /api/match/actions?chat_id=... — returns a list of active community actions.
    """
    db = get_db()
    try:
        actions_res = await _db(lambda: db.table("community_actions").select("*").eq("chat_id", chat_id).eq("is_active", True).execute())
        return {
            "actions": actions_res.data or []
        }
    except Exception as e:
        logger.error(f"Error fetching active actions for chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")



@router.post("/teams")
async def create_or_update_match_team(payload: TeamCreateOrUpdateSchema, team_id: str | None = None, user: dict = Depends(get_current_user)):
    """
    POST /api/match/teams — creates or updates game teams (game_teams). Requires group admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_game_admin_by_id(db, payload.game_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        game_res = await _db(lambda: db.table("games").select("group_id, chat_id").eq("id", payload.game_id).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        chat_id = game_res.data[0].get("group_id") or game_res.data[0].get("chat_id")

        data = {
            "chat_id": chat_id,
            "game_id": payload.game_id,
            "name": payload.name,
            "color": payload.color
        }

        if team_id:
            res = await _db(lambda: db.table("game_teams").update(data).eq("id", team_id).execute())
        else:
            res = await _db(lambda: db.table("game_teams").insert(data).execute())

        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to save team")
        return {"success": True, "team": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving match team: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lineups")
async def assign_match_lineup(payload: LineupAssignSchema, user: dict = Depends(get_current_user)):
    """
    POST /api/match/lineups — assigns a player to a team lineup for a game (game_lineups). Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_game_admin_by_id(db, payload.game_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        game_res = await _db(lambda: db.table("games").select("group_id, chat_id").eq("id", payload.game_id).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        chat_id = game_res.data[0].get("group_id") or game_res.data[0].get("chat_id")

        data = {
            "chat_id": chat_id,
            "game_id": payload.game_id,
            "team_id": payload.team_id,
            "player_id": payload.player_id
        }

        existing = await _db(lambda: db.table("game_lineups").select("id").eq("game_id", payload.game_id).eq("player_id", payload.player_id).execute())
        if existing.data:
            lineup_id = existing.data[0]["id"]
            res = await _db(lambda: db.table("game_lineups").update({"team_id": payload.team_id}).eq("id", lineup_id).execute())
        else:
            res = await _db(lambda: db.table("game_lineups").insert(data).execute())

        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to assign lineup")
        return {"success": True, "lineup": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning lineup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lineups/replace")
async def replace_match_lineup(payload: LineupReplaceSchema, user: dict = Depends(get_current_user)):
    """
    POST /api/match/lineups/replace — replaces one player with another in game lineups (game_lineups). Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_game_admin_by_id(db, payload.game_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        existing = await _db(lambda: db.table("game_lineups").select("*").eq("game_id", payload.game_id).eq("player_id", payload.old_player_id).execute())
        if not existing.data:
            raise HTTPException(status_code=404, detail="Old player lineup not found")

        old_lineup = existing.data[0]
        team_id = payload.team_id or old_lineup.get("team_id")

        new_existing = await _db(lambda: db.table("game_lineups").select("id").eq("game_id", payload.game_id).eq("player_id", payload.new_player_id).execute())

        if new_existing.data:
            new_lineup_id = new_existing.data[0]["id"]
            res = await _db(lambda: db.table("game_lineups").update({"team_id": team_id}).eq("id", new_lineup_id).execute())
            await _db(lambda: db.table("game_lineups").delete().eq("id", old_lineup["id"]).execute())
        else:
            res = await _db(lambda: db.table("game_lineups").update({"player_id": payload.new_player_id, "team_id": team_id}).eq("id", old_lineup["id"]).execute())

        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to replace lineup")
        res_updated = await _db(lambda: db.table("game_lineups").select("*").eq("game_id", payload.game_id).eq("player_id", payload.new_player_id).execute())
        return {"success": True, "lineup": res_updated.data[0] if res_updated.data else res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error replacing lineup: {e}", exc_info=True)
@router.post("/matches")
async def create_match(payload: MatchCreateSchema, user: dict = Depends(get_current_user)):
    """
    POST /api/match/matches — creates a new match/set (game_matches). Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_game_admin_by_id(db, payload.game_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        game_res = await _db(lambda: db.table("games").select("group_id, chat_id").eq("id", payload.game_id).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        chat_id = game_res.data[0].get("group_id") or game_res.data[0].get("chat_id")

        data = {
            "chat_id": chat_id,
            "game_id": payload.game_id,
            "left_team_id": payload.left_team_id,
            "right_team_id": payload.right_team_id,
            "left_score": 0,
            "right_score": 0,
            "status": "live"
        }

        res = await _db(lambda: db.table("game_matches").insert(data).execute())
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to create match")
        return {"success": True, "match": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating match: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/matches/{match_id}/score")
async def update_match_score(match_id: str, payload: MatchScoreUpdateSchema, user: dict = Depends(get_current_user)):
    """
    PATCH /api/match/matches/{match_id}/score — updates match score and status (game_matches). Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    try:
        match_res = await _db(lambda: db.table("game_matches").select("*").eq("id", match_id).execute())
        if not match_res.data:
            raise HTTPException(status_code=404, detail="Match not found")
        match_obj = match_res.data[0]
        game_id = match_obj.get("game_id")

        if not await _check_game_admin_by_id(db, game_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        update_data = {
            "left_score": payload.left_score,
            "right_score": payload.right_score
        }
        if payload.status:
            update_data["status"] = payload.status

        res = await _db(lambda: db.table("game_matches").update(update_data).eq("id", match_id).execute())
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to update match score")
        return {"success": True, "match": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating match score for {match_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logs")
async def create_action_log(payload: ActionLogSchema, user: dict = Depends(get_current_user)):
    """
    POST /api/match/logs — records player action in game_action_logs. Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_game_admin_by_id(db, payload.game_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        game_res = await _db(lambda: db.table("games").select("group_id, chat_id").eq("id", payload.game_id).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        chat_id = game_res.data[0].get("group_id") or game_res.data[0].get("chat_id")

        data = {
            "chat_id": chat_id,
            "game_id": payload.game_id,
            "match_id": payload.match_id,
            "action_type": payload.action_type,
            "actor_id": payload.actor_id or user_id,
            "payload": payload.payload
        }

        res = await _db(lambda: db.table("game_action_logs").insert(data).execute())
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to log action")
        return {"success": True, "action_log": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logs/undo")
async def undo_last_action_log(game_id: str, user: dict = Depends(get_current_user)):
    """
    POST /api/match/logs/undo — reverts the latest active action log. Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_game_admin_by_id(db, game_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        logs_res = await _db(lambda: db.table("game_action_logs").select("*").eq("game_id", game_id).order("created_at", desc=True).limit(1).execute())
        if not logs_res.data:
            raise HTTPException(status_code=404, detail="No action logs found to undo")

        last_log = logs_res.data[0]
        del_res = await _db(lambda: db.table("game_action_logs").delete().eq("id", last_log["id"]).execute())
        return {"success": True, "undone_action": last_log}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error undoing last action log for game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/community-actions")
async def create_or_update_community_action(payload: CommunityActionSchema, action_id: str | None = None, user: dict = Depends(get_current_user)):
    """
    POST /api/match/community-actions — adds or updates community actions (community_actions). Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    if not await _check_chat_admin(db, payload.chat_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

    try:
        data = {
            "chat_id": payload.chat_id,
            "title": payload.title,
            "description": payload.description,
            "is_active": payload.is_active
        }

        if action_id:
            res = await _db(lambda: db.table("community_actions").update(data).eq("id", action_id).execute())
        else:
            res = await _db(lambda: db.table("community_actions").insert(data).execute())

        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to save community action")
        return {"success": True, "community_action": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving community action: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/community-actions/{action_id}")
async def delete_community_action(action_id: str, user: dict = Depends(get_current_user)):
    """
    DELETE /api/match/community-actions/{action_id} — deactivates a community action. Requires admin rights.
    """
    db = get_db()
    user_id = user.get("id")

    try:
        action_res = await _db(lambda: db.table("community_actions").select("*").eq("id", action_id).execute())
        if not action_res.data:
            raise HTTPException(status_code=404, detail="Community action not found")

        action_obj = action_res.data[0]
        chat_id = action_obj.get("chat_id")

        if not await _check_chat_admin(db, chat_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        res = await _db(lambda: db.table("community_actions").update({"is_active": False}).eq("id", action_id).execute())
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to deactivate community action")
        return {"success": True, "community_action": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting community action {action_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

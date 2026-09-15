from aiohttp import web
from storage import get_chat_data, update_chat_data
from loader import bot
from utils import update_group_announcement

async def api_get_match_status(request: web.Request) -> web.Response:
    chat_id = request.query.get("chat_id")
    user_id = request.query.get("user_id")
    
    if not chat_id or not user_id:
        return web.json_response({"error": "Missing parameters"}, status=400)
        
    chat_data = get_chat_data(chat_id)
    if not chat_data:
        return web.json_response({"error": "Match not found"}, status=404)
        
    players = chat_data.get("players", {})
    reserve = chat_data.get("reserve", {})
    max_players = int(chat_data.get("match_details", {}).get("max_players", 12))
    
    user_status = "none"
    if user_id in players:
        user_status = "player"
    elif user_id in reserve:
        user_status = "reserve"

    return web.json_response({
        "group_title": chat_data.get("group_title", "Матч"),
        "players_count": len(players),
        "max_players": max_players,
        "players": list(players.values()),
        "reserve": list(reserve.values()),
        "user_status": user_status,
        "is_paid": players.get(user_id, {}).get("paid", False) if user_status == "player" else False
    })

async def api_handle_action(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
        
    chat_id = str(data.get("chat_id"))
    user_id = str(data.get("user_id"))
    full_name = data.get("full_name")
    username = data.get("username")
    action = data.get("action")
    
    chat_data = get_chat_data(chat_id)
    if not chat_data:
        return web.json_response({"error": "Match not found"}, status=404)
        
    players = chat_data.setdefault("players", {})
    reserve = chat_data.setdefault("reserve", {})
    max_players = int(chat_data.get("match_details", {}).get("max_players", 12))
    
    if action == "signup":
        if user_id not in players and user_id not in reserve:
            if len(players) < max_players:
                players[user_id] = {"name": full_name, "username": username, "paid": False}
            else:
                reserve[user_id] = {"name": full_name, "username": username}
    elif action == "cancel":
        if user_id in players:
            players.pop(user_id)
            if reserve:
                r_uid, r_data = next(iter(reserve.items()))
                del reserve[r_uid]
                players[r_uid] = {"name": r_data["name"], "username": r_data.get("username"), "paid": False}
        elif user_id in reserve:
            reserve.pop(user_id)
            
    update_chat_data(chat_id, chat_data)
    await update_group_announcement(bot, chat_id)
    
    return web.json_response({"status": "ok"})

def setup_api_routes(app: web.Application):
    app.router.add_get("/api/match", api_get_match_status)
    app.router.add_post("/api/action", api_handle_action)
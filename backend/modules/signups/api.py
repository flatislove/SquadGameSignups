from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from backend.core.auth import get_current_user, verify_chat_admin, is_superuser
from backend.core.config import settings
from backend.core.db import get_db
from backend.core.telegram_gateway import telegram_gateway
import asyncio
import logging
import time

router = APIRouter(prefix="/api/signups", tags=["signups"])
logger = logging.getLogger(__name__)

_tg_names_cache: dict[int, str] = {}
_background_tasks: set[asyncio.Task] = set()


async def _db(fn):
    """Runs synchronous Supabase client calls in a worker thread to avoid blocking event loop."""
    return await asyncio.to_thread(fn)


def _schedule_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class SignupSchema(BaseModel):
    game_id: str


class PlayerCreateOrUpdateSchema(BaseModel):
    name: str
    gender: str
    chat_id: int | None = None
    telegram_id: int | None = None
    telegram_username: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned:
            raise ValueError("Имя обязательно")
        return cleaned

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        val = (v or "").strip().lower()
        if val not in ("male", "female", "м", "ж"):
            raise ValueError("Пол обязателен (male/female)")
        return "male" if val in ("male", "м") else "female"

    @field_validator("telegram_username")
    @classmethod
    def clean_username(cls, v: str | None) -> str | None:
        if not v:
            return None
        cleaned = v.strip().lstrip("@")
        return cleaned or None


class AdminAddSignupSchema(BaseModel):
    game_id: str
    player_id: str | None = None
    name: str | None = None
    gender: str | None = None
    telegram_id: int | None = None
    telegram_username: str | None = None
    is_paid: bool = False


class TogglePaySchema(BaseModel):
    is_paid: bool


def _format_tg_user_name(chat_or_user) -> str | None:
    if not chat_or_user:
        return None
    full_name = " ".join(
        p for p in [getattr(chat_or_user, "first_name", None), getattr(chat_or_user, "last_name", None)] if p
    ).strip()
    if full_name:
        return full_name
    username = getattr(chat_or_user, "username", None)
    if username:
        return f"@{username}"
    title = getattr(chat_or_user, "title", None)
    if title:
        return title
    return None


async def _fetch_missing_tg_names_in_bg(user_ids: list[int]) -> None:
    bot = getattr(telegram_gateway, "_bot", None)
    if not bot:
        return
    for uid in user_ids:
        if uid in _tg_names_cache:
            continue
        try:
            tg_chat = await bot.get_chat(uid)
            name = _format_tg_user_name(tg_chat)
            if name:
                _tg_names_cache[uid] = name
        except Exception as e:
            logger.debug(f"Could not fetch Telegram name for user_id={uid}: {e}")


async def _enrich_signups(db, game_id: str, signups: list[dict]) -> list[dict]:
    player_ids = list({str(s["player_id"]) for s in signups if s.get("player_id")})
    tg_ids_without_player = list({
        int(s["user_id"])
        for s in signups
        if not s.get("player_id") and s.get("user_id") is not None and int(s["user_id"]) > 0
    })

    players_by_id: dict[str, dict] = {}
    players_by_tg: dict[int, dict] = {}

    try:
        tasks = []
        if player_ids:
            tasks.append(_db(lambda: db.table("players").select("*").in_("id", player_ids).execute()))
        else:
            tasks.append(asyncio.sleep(0, result=None))

        if tg_ids_without_player:
            tasks.append(_db(lambda: db.table("players").select("*").in_("telegram_id", tg_ids_without_player).execute()))
        else:
            tasks.append(asyncio.sleep(0, result=None))

        p_res, p_tg_res = await asyncio.gather(*tasks)

        if p_res and getattr(p_res, "data", None):
            for p in p_res.data:
                players_by_id[str(p["id"])] = p

        if p_tg_res and getattr(p_tg_res, "data", None):
            for p in p_tg_res.data:
                if p.get("telegram_id") is not None:
                    players_by_tg[int(p["telegram_id"])] = p
    except Exception as e:
        logger.warning(f"Failed to load players for game {game_id}: {e}")

    missing_tg_ids: list[int] = []

    for s in signups:
        uid = s.get("user_id")
        pid = str(s["player_id"]) if s.get("player_id") else None
        player_rec = players_by_id.get(pid) if pid else None
        if not player_rec and uid is not None and int(uid) > 0:
            player_rec = players_by_tg.get(int(uid))

        if player_rec:
            s["player_id"] = player_rec.get("id")
            s["user_name"] = player_rec.get("name") or s.get("user_name")
            s["gender"] = player_rec.get("gender")
            s["telegram_id"] = player_rec.get("telegram_id")
            s["telegram_username"] = player_rec.get("telegram_username")

        if not s.get("user_name"):
            if uid is not None and int(uid) > 0:
                cached_name = _tg_names_cache.get(int(uid))
                if cached_name:
                    s["user_name"] = cached_name
                else:
                    missing_tg_ids.append(int(uid))
                    s["user_name"] = "Участник"
            else:
                s["user_name"] = "Участник"

        if "is_paid" not in s:
            s["is_paid"] = bool(s.get("paid", False))

    if missing_tg_ids:
        _schedule_background(_fetch_missing_tg_names_in_bg(missing_tg_ids[:10]))

    return signups


async def _check_game_admin(game: dict, user_id: int | None) -> bool:
    if is_superuser(user_id):
        return True
    chat_id = game.get("group_id") or game.get("chat_id")
    bot = getattr(telegram_gateway, "_bot", None)
    if not chat_id or user_id is None or not bot:
        return False
    try:
        return bool(await verify_chat_admin(bot, int(chat_id), int(user_id)))
    except Exception as e:
        logger.warning(f"Failed to check admin rights for user {user_id} in chat {chat_id}: {e}")
        return False


async def _sync_announcement_message(game_id: str) -> None:
    db = get_db()
    try:
        game_res = await _db(lambda: db.table("games").select("*").eq("id", game_id).execute())
        if not game_res.data:
            return
        game = game_res.data[0]
        chat_id = game.get("group_id") or game.get("chat_id")
        message_id = game.get("message_id")
        if not chat_id or not message_id:
            return

        signups_res = await _db(lambda: db.table("signups").select("status").eq("game_id", game_id).execute())
        rows = signups_res.data or []
        main_count = sum(1 for r in rows if r.get("status") == "main")
        reserve_count = sum(1 for r in rows if r.get("status") == "reserve")

        await telegram_gateway.update_game_announcement(
            chat_id=int(chat_id),
            message_id=int(message_id),
            game_id=str(game_id),
            game_data=game,
            bot_username=settings.BOT_USERNAME,
            main_count=main_count,
            reserve_count=reserve_count,
        )
    except Exception as e:
        logger.warning(f"Failed to sync announcement message for game {game_id}: {e}")


@router.get("/players")
async def list_players(chat_id: int | None = None, search: str | None = None, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        query = db.table("players").select("*")
        if chat_id:
            query = query.eq("chat_id", chat_id)
        
        res = await _db(lambda: query.order("name", desc=False).execute())
        players = res.data or []
        if search and search.strip():
            q = search.strip().lower()
            players = [
                p for p in players
                if q in str(p.get("name") or "").lower()
                or q in str(p.get("telegram_username") or "").lower()
                or q in str(p.get("telegram_id") or "")
            ]
        return {"players": players}
    except Exception as e:
        logger.error(f"Error listing players: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/players")
async def create_player(payload: PlayerCreateOrUpdateSchema, user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        if payload.telegram_id is not None and payload.chat_id is not None:
            existing = await _db(
                lambda: db.table("players")
                .select("id")
                .eq("telegram_id", payload.telegram_id)
                .eq("chat_id", payload.chat_id)
                .execute()
            )
            if existing.data:
                raise HTTPException(status_code=400, detail="Игрок с таким Telegram ID уже существует в этом чате")

        insert_data = {
            "chat_id": payload.chat_id,
            "name": payload.name,
            "gender": payload.gender,
            "telegram_id": payload.telegram_id,
            "telegram_username": payload.telegram_username,
        }
        res = await _db(lambda: db.table("players").insert(insert_data).execute())
        if not res.data:
            raise HTTPException(status_code=500, detail="Не удалось сохранить игрока в базу")
        return {"success": True, "player": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating player: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/players/{player_id}")
async def update_player(
    player_id: str,
    payload: PlayerCreateOrUpdateSchema,
    game_id: str | None = None,
    user: dict = Depends(get_current_user),
):
    user_id = user.get("id")
    db = get_db()
    try:
        if game_id:
            game_res = await _db(lambda: db.table("games").select("*").eq("id", game_id).execute())
            if game_res.data and not await _check_game_admin(game_res.data[0], user_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        if payload.telegram_id is not None and payload.chat_id is not None:
            dup = await _db(
                lambda: db.table("players")
                .select("id")
                .eq("telegram_id", payload.telegram_id)
                .eq("chat_id", payload.chat_id)
                .neq("id", player_id)
                .execute()
            )
            if dup.data:
                raise HTTPException(status_code=400, detail="Другой игрок в этом чате уже использует этот Telegram ID")

        update_data = {
            "chat_id": payload.chat_id,
            "name": payload.name,
            "gender": payload.gender,
            "telegram_id": payload.telegram_id,
            "telegram_username": payload.telegram_username,
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}
        res = await _db(lambda: db.table("players").update(update_data).eq("id", player_id).execute())
        if not res.data:
            raise HTTPException(status_code=404, detail="Игрок не найден")

        if payload.telegram_id is not None:
            try:
                await _db(
                    lambda: db.table("signups")
                    .update({"user_id": payload.telegram_id, "user_name": payload.name})
                    .eq("player_id", player_id)
                    .execute()
                )
            except Exception:
                pass

        return {"success": True, "player": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating player {player_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_signup_status(game_id: str, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        game_res, signups_res = await asyncio.gather(
            _db(lambda: db.table("games").select("*").eq("id", game_id).execute()),
            _db(lambda: db.table("signups").select("*").eq("game_id", game_id).order("created_at", desc=False).execute()),
        )

        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]
        max_players = game.get("max_players") or 0

        signups, is_admin = await asyncio.gather(
            _enrich_signups(db, game_id, signups_res.data or []),
            _check_game_admin(game, user_id),
        )

        main_list = [s for s in signups if s.get("status") == "main"]
        reserve_list = [s for s in signups if s.get("status") == "reserve"]

        user_signup = next((s for s in signups if s.get("user_id") == user_id), None)

        status_val = "not_registered"
        message = f"Свободных мест: {max(0, max_players - len(main_list))}"

        if user_signup:
            if user_signup.get("status") == "main":
                status_val = "main"
                message = "✅ Вы записаны в ОСНОВНОЙ состав!"
            else:
                status_val = "reserve"
                message = "⚠️ Мест нет, вы находитесь в РЕЗЕРВЕ."

        return {
            "status": status_val,
            "message": message,
            "main_count": len(main_list),
            "reserve_count": len(reserve_list),
            "max_players": max_players,
            "game": game,
            "signups": signups,
            "is_admin": is_admin,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting signup status for game {game_id}, user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("")
async def cancel_signup(game_id: str, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        await _db(lambda: db.table("signups").delete().eq("game_id", game_id).eq("user_id", user_id).execute())

        game_res, signups_res = await asyncio.gather(
            _db(lambda: db.table("games").select("max_players").eq("id", game_id).execute()),
            _db(lambda: db.table("signups").select("*").eq("game_id", game_id).order("created_at", desc=False).execute()),
        )

        if game_res.data:
            max_players = game_res.data[0].get("max_players") or 0
            all_signups = signups_res.data or []
            main_list = [s for s in all_signups if s.get("status") == "main"]
            reserve_list = [s for s in all_signups if s.get("status") == "reserve"]

            if len(main_list) < max_players and reserve_list:
                first_reserve = reserve_list[0]
                await _db(lambda: db.table("signups").update({"status": "main"}).eq("id", first_reserve["id"]).execute())

        _schedule_background(_sync_announcement_message(game_id))
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
        existing, game_res, main_res = await asyncio.gather(
            _db(lambda: db.table("signups").select("status").eq("game_id", game_id).eq("user_id", user_id).execute()),
            _db(lambda: db.table("games").select("max_players, group_id").eq("id", game_id).execute()),
            _db(lambda: db.table("signups").select("id").eq("game_id", game_id).eq("status", "main").execute()),
        )

        if existing.data:
            return {"success": True, "status": existing.data[0]["status"]}

        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        
        game = game_res.data[0]
        max_players = game.get("max_players") or 0
        chat_id = game.get("group_id")

        main_count = len(main_res.data) if main_res.data else 0
        signup_status = "main" if main_count < max_players else "reserve"

        tg_name = _format_tg_user_name(type("TgUser", (), user)()) or "Участник"
        tg_username = (user.get("username") or "").strip().lstrip("@") or None

        player_id = None
        if user_id is not None:
            _tg_names_cache[int(user_id)] = tg_name
            try:
                p_res = await _db(lambda: db.table("players").select("id,name").eq("telegram_id", int(user_id)).eq("chat_id", chat_id).execute())
                if p_res.data:
                    player_id = p_res.data[0]["id"]
                    tg_name = p_res.data[0].get("name") or tg_name
                else:
                    created_p = await _db(
                        lambda: db.table("players")
                        .insert(
                            {
                                "chat_id": chat_id,
                                "name": tg_name,
                                "gender": "male",
                                "telegram_id": int(user_id),
                                "telegram_username": tg_username,
                            }
                        )
                        .execute()
                    )
                    if created_p.data:
                        player_id = created_p.data[0]["id"]
            except Exception as pe:
                logger.warning(f"Could not sync player in players table for user {user_id}: {pe}")

        row = {
            "game_id": game_id,
            "user_id": user_id,
            "player_id": player_id,
            "user_name": tg_name,
            "status": signup_status,
            "is_paid": False,
        }
        try:
            await _db(lambda: db.table("signups").insert(row).execute())
        except Exception:
            row.pop("player_id", None)
            row.pop("user_name", None)
            await _db(lambda: db.table("signups").insert(row).execute())

        _schedule_background(_sync_announcement_message(game_id))
        return {"success": True, "status": signup_status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error signing up user {user_id} for game {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/admin-add")
async def admin_add_signup(payload: AdminAddSignupSchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        game_res = await _db(lambda: db.table("games").select("*").eq("id", payload.game_id).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]
        chat_id = game.get("group_id") or game.get("chat_id")

        if not await _check_game_admin(game, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        player_record = None
        if payload.player_id:
            p_res = await _db(lambda: db.table("players").select("*").eq("id", payload.player_id).execute())
            if not p_res.data:
                raise HTTPException(status_code=404, detail="Игрок не найден в базе")
            player_record = p_res.data[0]
        else:
            validated = PlayerCreateOrUpdateSchema(
                name=payload.name or "",
                gender=payload.gender or "",
                chat_id=chat_id,
                telegram_id=payload.telegram_id,
                telegram_username=payload.telegram_username,
            )
            if validated.telegram_id is not None:
                dup = await _db(lambda: db.table("players").select("*").eq("telegram_id", validated.telegram_id).eq("chat_id", chat_id).execute())
                if dup.data:
                    player_record = dup.data[0]
            if not player_record:
                ins = await _db(
                    lambda: db.table("players")
                    .insert(
                        {
                            "chat_id": chat_id,
                            "name": validated.name,
                            "gender": validated.gender,
                            "telegram_id": validated.telegram_id,
                            "telegram_username": validated.telegram_username,
                        }
                    )
                    .execute()
                )
                if not ins.data:
                    raise HTTPException(status_code=500, detail="Не удалось создать игрока в базе")
                player_record = ins.data[0]

        signups_res = await _db(lambda: db.table("signups").select("*").eq("game_id", payload.game_id).execute())
        existing_signups = signups_res.data or []

        already_in_game = any(
            (s.get("player_id") and str(s.get("player_id")) == str(player_record["id"]))
            or (
                player_record.get("telegram_id") is not None
                and s.get("user_id") is not None
                and int(s["user_id"]) == int(player_record["telegram_id"])
            )
            for s in existing_signups
        )
        if already_in_game:
            raise HTTPException(status_code=400, detail="Этот игрок уже есть в списке матча")

        max_players = game.get("max_players") or 0
        main_count = sum(1 for s in existing_signups if s.get("status") == "main")
        signup_status = "main" if main_count < max_players else "reserve"

        effective_user_id = (
            int(player_record["telegram_id"])
            if player_record.get("telegram_id") is not None
            else -int(time.time() * 1000)
        )

        insert_data = {
            "game_id": payload.game_id,
            "player_id": player_record["id"],
            "user_id": effective_user_id,
            "user_name": player_record["name"],
            "status": signup_status,
            "is_paid": bool(payload.is_paid),
        }
        try:
            await _db(lambda: db.table("signups").insert(insert_data).execute())
        except Exception:
            insert_data.pop("player_id", None)
            insert_data.pop("user_name", None)
            await _db(lambda: db.table("signups").insert(insert_data).execute())

        _schedule_background(_sync_announcement_message(payload.game_id))
        return {"success": True, "status": signup_status, "player": player_record}

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in admin_add_signup for game {payload.game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{signup_id}/pay")
async def toggle_signup_payment(signup_id: str, payload: TogglePaySchema, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        s_res = await _db(lambda: db.table("signups").select("id,game_id").eq("id", signup_id).execute())
        if not s_res.data:
            raise HTTPException(status_code=404, detail="Signup not found")
        signup = s_res.data[0]

        game_res = await _db(lambda: db.table("games").select("*").eq("id", signup["game_id"]).execute())
        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")

        if not await _check_game_admin(game_res.data[0], user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        await _db(lambda: db.table("signups").update({"is_paid": bool(payload.is_paid)}).eq("id", signup_id).execute())
        return {"success": True, "is_paid": bool(payload.is_paid)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling payment for signup {signup_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{signup_id}/admin-remove")
async def admin_remove_signup(signup_id: str, user: dict = Depends(get_current_user)):
    user_id = user.get("id")
    db = get_db()

    try:
        s_res = await _db(lambda: db.table("signups").select("id,game_id").eq("id", signup_id).execute())
        if not s_res.data:
            raise HTTPException(status_code=404, detail="Signup not found")
        signup = s_res.data[0]
        game_id = signup["game_id"]

        game_res, all_res = await asyncio.gather(
            _db(lambda: db.table("games").select("max_players,group_id,chat_id").eq("id", game_id).execute()),
            _db(lambda: db.table("signups").select("id,status").eq("game_id", game_id).order("created_at", desc=False).execute()),
        )

        if not game_res.data:
            raise HTTPException(status_code=404, detail="Game not found")
        game = game_res.data[0]

        if not await _check_game_admin(game, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin rights required")

        await _db(lambda: db.table("signups").delete().eq("id", signup_id).execute())

        max_players = game.get("max_players") or 0
        remaining = [s for s in (all_res.data or []) if str(s.get("id")) != str(signup_id)]
        main_list = [s for s in remaining if s.get("status") == "main"]
        reserve_list = [s for s in remaining if s.get("status") == "reserve"]

        if len(main_list) < max_players and reserve_list:
            await _db(lambda: db.table("signups").update({"status": "main"}).eq("id", reserve_list[0]["id"]).execute())

        _schedule_background(_sync_announcement_message(game_id))
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing signup {signup_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
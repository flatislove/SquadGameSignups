from datetime import timezone, timedelta
from aiogram import types

LOCAL_TZ = timezone(timedelta(hours=5))

def escape_md(text: str) -> str:
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text

def build_announcement_text(chat_data: dict):
    details = chat_data.get("match_details", {
        "date": "TBD", "time": "TBD", "end_time": "TBD",
        "loc_name": "TBD", "loc_link": "", "cost": "0",
        "phone": "TBD", "name": "TBD", "max_players": 12
    })
    
    max_p = int(details.get("max_players", 12))
    players = chat_data.get("players", {})
    reserve = chat_data.get("reserve", {})
    
    players_lines = []
    player_items = list(players.items())
    for i, (uid, pdata) in enumerate(player_items):
        full_name = pdata["name"]
        safe_name = escape_md(full_name)
        username = pdata.get("username")
        
        if username:
            clean_username = username.lstrip("@")
            user_link = f"[{safe_name}](https://t.me/{clean_username})"
        elif str(uid).startswith("manual_") or not str(uid).isdigit():
            user_link = safe_name
        else:
            user_link = f"[{safe_name}](tg://user?id={uid})"
            
        paid_mark = "🟩" if pdata.get("paid", False) else "🟧"
        players_lines.append(f"{paid_mark} {i+1}. {user_link}")
        
    players_list_text = "\n".join(players_lines) if players_lines else "_Пока нет участников._"
        
    reserve_lines = []
    reserve_items = list(reserve.items())
    for i, (uid, rdata) in enumerate(reserve_items):
        full_name = rdata["name"]
        safe_name = escape_md(full_name)
        username = rdata.get("username")
        
        if username:
            clean_username = username.lstrip("@")
            user_link = f"[{safe_name}](https://t.me/{clean_username})"
        elif str(uid).startswith("manual_") or not str(uid).isdigit():
            user_link = safe_name
        else:
            user_link = f"[{safe_name}](tg://user?id={uid})"
            
        reserve_lines.append(f"🟦 {i+1}. {user_link}")
        
    reserve_section = ""
    if reserve_lines:
        reserve_section = f"\n\n*Резерв ({len(reserve)}):*\n" + "\n".join(reserve_lines)

    loc_display = f"[{details['loc_name']}]({details['loc_link']})" if details.get('loc_link') else details['loc_name']
    time_display = f"{details['time']} - {details['end_time']}" if details.get('end_time') else details['time']
    
    total_count = len(players)
    
    return (
        f"🏐 *Волейбол* (Основной состав: {total_count}/{max_p})\n\n"
        f"📅 *Дата:* {details['date']}\n"
        f"⏰ *Время:* {time_display}\n"
        f"📍 *Место:* {loc_display}\n"
        f"💰 *Стоимость:* {details['cost']} KZT\n"
        f"💳 {details['phone']} ({details['name']})\n\n"
        f"*Участники:*\n{players_list_text}"
        f"{reserve_section}"
    )

async def update_group_announcement(bot, chat_id: str):
    from storage import get_chat_data
    from keyboards import get_match_keyboard
    
    chat_data = get_chat_data(chat_id)
    msg_id = chat_data.get("announcement_message_id")
    if not msg_id:
        return
    try:
        await bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(msg_id),
            text=build_announcement_text(chat_data),
            parse_mode="Markdown",
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            reply_markup=get_match_keyboard()
        )
    except Exception as e:
        print(f"Failed to update group announcement: {e}")

async def get_user_admin_groups(bot, user_id: int):
    from storage import load_data
    data = load_data()
    groups = data.get("groups", {})
    admin_groups = []
    for chat_id, chat_data in groups.items():
        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user_id)
            if member.status in ["creator", "administrator"]:
                title = chat_data.get("group_title", f"Группа {chat_id}")
                admin_groups.append((chat_id, title))
        except Exception:
            continue
    return admin_groups
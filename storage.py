import json
import os

DB_FILE = "data.json"

def load_data():
    if not os.path.exists(DB_FILE):
        return {"chats": {}, "linked_chat_id": None}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "chats" not in data:
                data["chats"] = {}
            if "linked_chat_id" not in data:
                data["linked_chat_id"] = None
            return data
    except json.JSONDecodeError:
        return {"chats": {}, "linked_chat_id": None}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_chat_data(chat_id: str):
    data = load_data()
    chats = data.setdefault("chats", {})
    if str(chat_id) not in chats:
        chats[str(chat_id)] = {
            "active_match": None,
            "players": {}
        }
        save_data(data)
    return chats[str(chat_id)]

def update_chat_data(chat_id: str, chat_data):
    data = load_data()
    data.setdefault("chats", {})[str(chat_id)] = chat_data
    save_data(data)
import json
import os

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_chat_data(chat_id: str):
    data = load_data()
    groups = data.setdefault("groups", {})
    return groups.setdefault(str(chat_id), {})

def update_chat_data(chat_id: str, chat_data: dict):
    data = load_data()
    groups = data.setdefault("groups", {})
    groups[str(chat_id)] = chat_data
    save_data(data)
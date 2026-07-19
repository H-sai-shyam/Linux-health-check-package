import json
from datetime import datetime
from pathlib import Path

from linux_health.config import HISTORY_FILE


def get_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def add_entry(entry: dict) -> None:
    history = get_history()
    entry["date"] = datetime.now().strftime("%d-%m-%Y")
    history.insert(0, entry)
    history = history[:50]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

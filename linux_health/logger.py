import json
import os
from datetime import datetime
from pathlib import Path

from linux_health.config import LOG_DIR


def write_log(entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{timestamp}.json"
    entry["timestamp"] = datetime.now().isoformat()
    with open(log_file, "w") as f:
        json.dump(entry, f, indent=2)
    _cleanup_old_logs()


def _cleanup_old_logs(max_logs: int = 50) -> None:
    try:
        logs = sorted(LOG_DIR.glob("*.json"), key=os.path.getmtime)
        while len(logs) > max_logs:
            logs[0].unlink()
            logs = logs[1:]
    except Exception:
        pass


def get_logs() -> list[dict]:
    logs = []
    try:
        for f in sorted(LOG_DIR.glob("*.json"), reverse=True):
            try:
                with open(f) as fh:
                    logs.append(json.load(fh))
            except (json.JSONDecodeError, OSError):
                pass
    except OSError:
        pass
    return logs

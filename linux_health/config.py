import os
import tomllib
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "linux-health"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DATA_DIR = Path.home() / ".local" / "share" / "linux-health"
LOG_DIR = DATA_DIR / "logs"
HISTORY_FILE = DATA_DIR / "history.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "auto_cleanup": True,
    "cleanup_interval_days": 7,
    "notifications": True,
    "cleanup_cache": True,
    "cleanup_pacman": True,
    "cleanup_flatpak": True,
    "cleanup_tmp": True,
    "cleanup_journal": True,
    "cleanup_maven": False,
    "cleanup_gradle": False,
    "cleanup_docker": False,
    "cleanup_build": False,
    "cleanup_target": False,
    "warning_disk_percent": 80,
    "critical_disk_percent": 90,
    "large_file_threshold": "1GB",
    "max_logs": 50,
}


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                user_config = tomllib.load(f)
            config.update(user_config)
        except Exception:
            pass
    return config


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

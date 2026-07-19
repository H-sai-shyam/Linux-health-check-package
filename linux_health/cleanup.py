import shutil
import subprocess
from pathlib import Path

from linux_health.config import load_config
from linux_health.history import add_entry
from linux_health.logger import write_log
from linux_health.utils import get_dir_size, human_size


SAFE_CACHE_DIRS = {
    "pip",
    "yay",
    "paru",
    "go-build",
    "npm",
    "pnpm",
    "bun",
    "yarn",
    "cargo",
    "rustup",
    "node-gyp",
    "composer",
    "gem",
    "easy_install",
    "mypy",
    "black",
    "ruff",
    "pytest",
    "httpie",
    "wget",
    "curl",
    "ansible-lint",
}

SAFE_CACHE_GLOBS = [
    "*.cache",
    "*.tmp",
    "*.bak",
    "python*",
    "pip*",
]


def _is_protected(name: str) -> bool:
    protected = {
        "waybar", "fontconfig", "wal", "sway", "hyprland", "hypr",
        "gnome-shell", "plasma", "kde*", "events", "sessions",
        "mesa", "nv", "amd", "tracker3", "evolution",
        "gstreamer", "ibus", "dconf", "pulse", "pipewire",
        "wireplumber", "thumbnails", "mozilla", "chromium",
        "google-chrome", "brave-browser", "firefox", "thunderbird",
        "discord", "slack", "teams", "spotify", "code",
        "jetbrains", "intellij", "pycharm", "webstorm",
    }
    return name in protected or any(name.startswith(p.rstrip("*")) for p in protected if p.endswith("*"))


def clean_cache(dry_run: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    cache_dir = Path.home() / ".cache"
    if not cache_dir.exists():
        return result

    cleaned_any = False
    for item in cache_dir.iterdir():
        name = item.name
        if _is_protected(name):
            continue
        if name in SAFE_CACHE_DIRS:
            if dry_run:
                result["actions"].append(f"Would clean {name}")
            else:
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    cleaned_any = True
                except PermissionError:
                    pass
            continue

        is_hidden_tmp = name.startswith("tmp") or name.endswith(".tmp")
        is_old_log = name.endswith(".log") and item.is_file()
        if is_hidden_tmp or is_old_log:
            if dry_run:
                result["actions"].append(f"Would clean {name}")
            else:
                try:
                    item.unlink(missing_ok=True)
                    cleaned_any = True
                except PermissionError:
                    pass

    if not dry_run and cleaned_any:
        result["actions"].append("Cleaned safe cache directories")

    result["freed"] = 0
    return result


def clean_thumbnails(dry_run: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    thumb_dir = Path.home() / ".cache" / "thumbnails"
    if not thumb_dir.exists():
        return result

    size_before = get_dir_size(thumb_dir)

    if dry_run:
        result["actions"].append(f"Would clean thumbnail cache ({thumb_dir})")
    else:
        try:
            shutil.rmtree(thumb_dir, ignore_errors=True)
        except PermissionError:
            pass

    size_after = get_dir_size(thumb_dir)
    result["freed"] = size_before - size_after
    return result


def clean_tmp(dry_run: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    tmp = Path("/tmp")
    if not tmp.exists():
        return result

    size_before = get_dir_size(tmp)

    if dry_run:
        result["actions"].append("Would clean /tmp")
    else:
        try:
            for item in tmp.iterdir():
                if item.name in (".", ".."):
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except PermissionError:
                    pass
        except PermissionError:
            pass

    size_after = get_dir_size(tmp)
    result["freed"] = size_before - size_after
    return result


def clean_journal(dry_run: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    try:
        result_bytes = subprocess.run(
            ["journalctl", "--disk-usage"],
            capture_output=True, text=True, timeout=10,
        )
        size_before = 0
        if result_bytes.returncode == 0:
            for part in result_bytes.stdout.split():
                try:
                    size_before = int(part)
                    break
                except ValueError:
                    continue

        if dry_run:
            result["actions"].append("Would vacuum journal logs")
        else:
            subprocess.run(
                ["journalctl", "--vacuum-time=7d"],
                capture_output=True, text=True, timeout=30,
            )

        result_bytes_after = subprocess.run(
            ["journalctl", "--disk-usage"],
            capture_output=True, text=True, timeout=10,
        )
        size_after = 0
        if result_bytes_after.returncode == 0:
            for part in result_bytes_after.stdout.split():
                try:
                    size_after = int(part)
                    break
                except ValueError:
                    continue

        result["freed"] = max(0, size_before - size_after)
    except Exception:
        result["error"] = "Failed to clean journal"
    return result


def run_cleanup(dry_run: bool = False) -> dict:
    config = load_config()
    total_freed = 0
    all_actions: list[str] = []

    cleaners = []

    if config.get("cleanup_cache"):
        cleaners.append(("Cache", clean_cache))
        cleaners.append(("Thumbnails", clean_thumbnails))

    if config.get("cleanup_tmp"):
        cleaners.append(("Temporary files", clean_tmp))

    if config.get("cleanup_journal"):
        cleaners.append(("Journal logs", clean_journal))

    from linux_health.pacman import clean as clean_pacman
    if config.get("cleanup_pacman"):
        cleaners.append(("Pacman cache", lambda dr: clean_pacman(dr)))

    from linux_health.flatpak import clean as clean_flatpak
    if config.get("cleanup_flatpak"):
        cleaners.append(("Flatpak", lambda dr: clean_flatpak(dr)))

    from linux_health.docker import clean as clean_docker
    if config.get("cleanup_docker"):
        cleaners.append(("Docker", lambda dr: clean_docker(dr)))

    results = {}
    for name, cleaner in cleaners:
        r = cleaner(dry_run)
        results[name] = r
        total_freed += r.get("freed", 0)
        all_actions.extend(r.get("actions", []))

    summary = {
        "total_freed": total_freed,
        "total_freed_h": human_size(total_freed),
        "actions": all_actions,
        "results": results,
        "dry_run": dry_run,
    }

    if not dry_run:
        add_entry({"freed": total_freed, "freed_h": human_size(total_freed), "actions": all_actions})
        write_log(summary)

    return summary

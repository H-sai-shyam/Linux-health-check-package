import platform
from datetime import datetime, timedelta
from pathlib import Path

from linux_health import battery, cpu, disk, memory, network, temperature
from linux_health.utils import get_dir_size, human_size, command_exists, run_cmd


def get_system_info() -> dict:
    uptime_seconds = None
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
    except (OSError, ValueError):
        pass

    uptime_str = "N/A"
    if uptime_seconds is not None:
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        uptime_str = " ".join(parts) if parts else "Less than 1 hour"

    return {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
    }


def get_cache_sizes() -> dict:
    sizes: dict = {}
    cache_paths = {
        "user_cache": Path.home() / ".cache",
        "pacman": Path("/var/cache/pacman/pkg"),
        "flatpak": Path("/var/lib/flatpak"),
    }
    for key, path in cache_paths.items():
        sizes[key] = get_dir_size(path)
        sizes[f"{key}_h"] = human_size(sizes[key])

    thumbnail_cache = Path.home() / ".cache" / "thumbnails"
    sizes["thumbnails"] = get_dir_size(thumbnail_cache)
    sizes["thumbnails_h"] = human_size(sizes["thumbnails"])

    return sizes


def get_dev_sizes() -> dict:
    sizes: dict = {}
    paths = {
        "maven": Path.home() / ".m2",
        "gradle": Path.home() / ".gradle",
    }
    for key, path in paths.items():
        sizes[key] = get_dir_size(path)
        sizes[f"{key}_h"] = human_size(sizes[key])
    return sizes


def get_last_cleanup() -> str | None:
    from linux_health.history import get_history
    history = get_history()
    if history:
        return history[0].get("date")
    return None


def get_next_cleanup() -> str | None:
    from linux_health.config import load_config
    config = load_config()
    from linux_health.history import get_history
    history = get_history()
    if history:
        last_date = history[0].get("timestamp") or history[0].get("date")
        if last_date:
            try:
                if "T" in str(last_date):
                    last_dt = datetime.fromisoformat(last_date)
                else:
                    last_dt = datetime.strptime(str(last_date), "%d-%m-%Y")
                next_dt = last_dt + timedelta(days=config.get("cleanup_interval_days", 7))
                if next_dt < datetime.now():
                    return "Today"
                if next_dt.date() == datetime.now().date():
                    return "Today"
                if next_dt.date() == (datetime.now() + timedelta(days=1)).date():
                    return "Tomorrow"
                return next_dt.strftime("%d-%m-%Y")
            except (ValueError, TypeError):
                pass
    return "Today"


def collect_all() -> dict:
    return {
        "system": get_system_info(),
        "cpu": cpu.get_info(),
        "cpu_temp": cpu.get_temperature(),
        "ram": memory.get_ram_info(),
        "swap": memory.get_swap_info(),
        "battery": battery.get_info(),
        "disk": disk.get_disk_usage(),
        "disk_analysis": disk.analyze_disk(),
        "network": network.get_info(),
        "cache": get_cache_sizes(),
        "dev": get_dev_sizes(),
        "last_cleanup": get_last_cleanup(),
        "next_cleanup": get_next_cleanup(),
    }


def get_doctor_recommendations(data: dict) -> list[dict]:
    from linux_health.config import load_config
    config = load_config()
    warnings: list[dict] = []

    disk_usage = data.get("disk")
    if disk_usage:
        pct = disk_usage.get("percent", 0)
        if pct >= config.get("critical_disk_percent", 90):
            warnings.append({
                "severity": "critical",
                "message": f"Disk is {pct}% full. Free up space immediately.",
            })
        elif pct >= config.get("warning_disk_percent", 80):
            warnings.append({
                "severity": "warning",
                "message": f"Disk is {pct}% full. Consider cleaning up.",
            })

    cpu_temp = data.get("cpu_temp")
    if cpu_temp is not None and cpu_temp > 85:
        warnings.append({
            "severity": "warning",
            "message": f"High CPU temperature: {cpu_temp}°C",
        })

    battery = data.get("battery", {})
    if battery.get("present") and battery.get("health") is not None:
        if battery["health"] < 60:
            warnings.append({
                "severity": "warning",
                "message": f"Battery health is only {battery['health']}%. Consider replacement.",
            })

    cache = data.get("cache", {})
    user_cache = cache.get("user_cache", 0)
    if user_cache > 5 * 1024**3:
        warnings.append({
            "severity": "info",
            "message": f"Large user cache: {cache.get('user_cache_h', 'N/A')}",
        })

    pacman = cache.get("pacman", 0)
    if pacman > 2 * 1024**3:
        warnings.append({
            "severity": "info",
            "message": f"Large pacman cache: {cache.get('pacman_h', 'N/A')}. Run paccache to clean.",
        })

    return warnings

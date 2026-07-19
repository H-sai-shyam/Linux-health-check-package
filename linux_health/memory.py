from linux_health.utils import human_size, bytes_percent


def get_ram_info() -> dict:
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
            "total_h": human_size(mem.total),
            "used_h": human_size(mem.used),
            "available_h": human_size(mem.available),
        }
    except ImportError:
        pass
    with open("/proc/meminfo") as f:
        data = f.read()
    lines = {}
    for line in data.splitlines():
        parts = line.split(":")
        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip().replace(" kB", "").strip()
            try:
                lines[key] = int(val) * 1024
            except ValueError:
                lines[key] = 0
    total = lines.get("MemTotal", 0)
    available = lines.get("MemAvailable", 0)
    used = total - available
    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": bytes_percent(used, total),
        "total_h": human_size(total),
        "used_h": human_size(used),
        "available_h": human_size(available),
    }


def get_swap_info() -> dict:
    try:
        import psutil
        swap = psutil.swap_memory()
        return {
            "total": swap.total,
            "used": swap.used,
            "percent": swap.percent,
            "total_h": human_size(swap.total),
            "used_h": human_size(swap.used),
        }
    except ImportError:
        pass
    with open("/proc/meminfo") as f:
        data = f.read()
    total = 0
    free = 0
    for line in data.splitlines():
        if line.startswith("SwapTotal:"):
            total = int(line.split()[1]) * 1024
        elif line.startswith("SwapFree:"):
            free = int(line.split()[1]) * 1024
    used = total - free
    return {
        "total": total,
        "used": used,
        "percent": bytes_percent(used, total),
        "total_h": human_size(total),
        "used_h": human_size(used),
    }

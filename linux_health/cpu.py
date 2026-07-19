from linux_health.utils import run_cmd


def get_info() -> dict:
    info: dict = {}
    try:
        import psutil
        info["usage"] = psutil.cpu_percent(interval=0.5)
        info["cores"] = psutil.cpu_count(logical=True)
        info["physical_cores"] = psutil.cpu_count(logical=False)
    except ImportError:
        usage = run_cmd(["sh", "-c",
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"])
        info["usage"] = float(usage) if usage else 0.0
        cores = run_cmd(["nproc"])
        info["cores"] = int(cores) if cores else 0
        info["physical_cores"] = info["cores"]
    return info


def get_temperature() -> float | None:
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        if "coretemp" in temps:
            return max(t.current for t in temps["coretemp"])
        if "k10temp" in temps:
            for t in temps["k10temp"]:
                if t.current > 0:
                    return t.current
    except (ImportError, AttributeError):
        pass
    try:
        result = run_cmd(["cat", "/sys/class/thermal/thermal_zone0/temp"])
        if result:
            return round(int(result) / 1000, 1)
    except Exception:
        pass
    return None

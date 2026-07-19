import subprocess

from linux_health.cpu import get_temperature as get_cpu_temperature


def get_gpu_temperature() -> float | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def get_all_temps() -> dict:
    temps: dict = {}
    cpu_temp = get_cpu_temperature()
    if cpu_temp is not None:
        temps["cpu"] = cpu_temp

    gpu_temp = get_gpu_temperature()
    if gpu_temp is not None:
        temps["gpu"] = gpu_temp

    return temps

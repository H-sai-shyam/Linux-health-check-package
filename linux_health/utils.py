import shutil
import subprocess
from pathlib import Path


def human_size(bytes_val: int) -> str:
    if bytes_val == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(bytes_val)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.1f}{units[i]}"


def parse_size(size_str: str) -> int:
    size_str = size_str.strip().upper()
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                num = float(size_str[: -len(unit)])
                return int(num * multiplier)
            except ValueError:
                pass
    try:
        return int(size_str)
    except ValueError:
        return 0


def get_dir_size(path: str | Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    try:
        result = subprocess.run(
            ["du", "-sb", str(path)], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except Exception:
        pass
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (PermissionError, OSError):
        pass
    return total


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run_cmd(args: list[str], timeout: int = 15) -> str | None:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def bytes_percent(used: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((used / total) * 100, 1)

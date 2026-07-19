import subprocess
from pathlib import Path

from linux_health.utils import run_cmd, human_size, get_dir_size, command_exists


def get_installed_kernels() -> list[dict]:
    kernels = []
    modules_dir = Path("/usr/lib/modules")
    if not modules_dir.exists():
        return kernels
    for entry in sorted(modules_dir.iterdir(), reverse=True):
        if entry.is_dir():
            size = get_dir_size(entry)
            kernels.append({
                "version": entry.name,
                "size": size,
                "size_h": human_size(size),
                "path": str(entry),
            })
    return kernels


def get_current_kernel() -> str:
    return run_cmd(["uname", "-r"]) or "N/A"


def get_latest_kernel_pkg() -> str | None:
    result = run_cmd(["pacman", "-Qi", "linux"], timeout=15)
    if result:
        for line in result.splitlines():
            if line.startswith("Version"):
                return line.split(":", 1)[-1].strip()
    return None


def vercmp(v1: str, v2: str) -> int:
    result = run_cmd(["vercmp", v1, v2], timeout=5)
    if result:
        try:
            return int(result.strip())
        except ValueError:
            pass
    return 0


def is_newer_kernel_available(current: str, latest: str) -> bool:
    return vercmp(latest, current) > 0


def get_boot_usage() -> dict | None:
    try:
        result = subprocess.run(
            ["df", "-B1", "/boot"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    pct = round((used / total) * 100, 1) if total else 0
                    return {
                        "total_h": human_size(total),
                        "used_h": human_size(used),
                        "free_h": human_size(free),
                        "percent": pct,
                    }
    except Exception:
        pass
    return None


def get_grub_config() -> dict | None:
    if not Path("/etc/default/grub").exists():
        return None
    info: dict = {}
    try:
        content = Path("/etc/default/grub").read_text()
        for line in content.splitlines():
            if "GRUB_DEFAULT=" in line:
                info["default"] = line.split("=", 1)[-1].strip().strip('"')
            elif "GRUB_TIMEOUT=" in line:
                info["timeout"] = line.split("=", 1)[-1].strip().strip('"')
            elif "GRUB_CMDLINE_LINUX_DEFAULT=" in line:
                cmdline = line.split("=", 1)[-1].strip().strip('"')
                info["cmdline"] = cmdline
    except Exception:
        pass
    return info


def get_systemd_analyze_blame() -> list[dict]:
    result = run_cmd(["systemd-analyze", "blame"], timeout=15)
    entries = []
    if result:
        for line in result.splitlines()[:15]:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                entries.append({"time": parts[0], "unit": parts[1]})
    return entries


def get_systemd_analyze_time() -> str | None:
    return run_cmd(["systemd-analyze", "time"], timeout=10)


def get_systemd_analyze_critical() -> list[dict]:
    result = run_cmd(["systemd-analyze", "critical-chain"], timeout=15)
    entries = []
    if result:
        for line in result.splitlines():
            if "@" in line:
                parts = line.strip().split()
                if len(parts) >= 1:
                    unit = parts[-1]
                    time_part = ""
                    for p in parts:
                        if "@" in p:
                            time_part = p
                            break
                    entries.append({"time": time_part, "unit": unit})
    return entries


def get_dmesg_errors() -> list[str]:
    try:
        result = subprocess.run(
            ["dmesg", "-l", "err", "-P"],
            capture_output=True, text=True, timeout=10,
        )
        errors = [l for l in result.stdout.splitlines() if l.strip()]
        return errors[-20:]
    except Exception:
        return []


def get_failed_services() -> list[str]:
    result = run_cmd(["systemctl", "--user", "--failed", "--plain", "--no-legend"], timeout=10)
    failed = []
    if result:
        for line in result.splitlines():
            parts = line.split()
            if parts:
                failed.append(parts[0])
    result2 = run_cmd(["systemctl", "--failed", "--plain", "--no-legend"], timeout=10)
    if result2:
        for line in result2.splitlines():
            parts = line.split()
            if parts and parts[0] not in failed:
                failed.append(parts[0])
    return failed


def get_old_kernels_for_removal() -> list[str]:
    current = get_current_kernel()
    kernels = get_installed_kernels()
    old = [k for k in kernels if k["version"] != current]
    return [k["version"] for k in old]


def collect_all() -> dict:
    data = {
        "current_kernel": get_current_kernel(),
        "latest_kernel_pkg": get_latest_kernel_pkg(),
        "installed_kernels": get_installed_kernels(),
        "old_kernels": get_old_kernels_for_removal(),
        "boot_usage": get_boot_usage(),
        "grub_config": get_grub_config(),
        "boot_time": get_systemd_analyze_time(),
        "blame": get_systemd_analyze_blame(),
        "critical_chain": get_systemd_analyze_critical(),
        "dmesg_errors": get_dmesg_errors(),
        "failed_services": get_failed_services(),
    }
    return data

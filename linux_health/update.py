import subprocess
import configparser
from pathlib import Path

from linux_health.utils import run_cmd, command_exists


def _pacman_conf_held() -> list[str]:
    held = []
    try:
        config = configparser.ConfigParser()
        config.read("/etc/pacman.conf")
        for section in config.sections():
            if config.has_option(section, "IgnorePkg"):
                for pkg in config.get(section, "IgnorePkg").split():
                    held.append(pkg.strip())
    except Exception:
        pass
    return held


def check_partial_upgrades() -> int:
    try:
        result = subprocess.run(
            ["pacman", "-Qk", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        errors = 0
        for line in result.stderr.splitlines():
            if "missing" in line or "ERROR" in line:
                errors += 1
        return errors
    except Exception:
        return -1


def check_orphans() -> list[str]:
    result = run_cmd(["pacman", "-Qtdq"], timeout=15)
    if result:
        return [p for p in result.splitlines() if p.strip()]
    return []


def check_aur_updates() -> dict:
    aur = {"available": False, "count": 0}
    if command_exists("yay"):
        aur["available"] = True
        result = run_cmd(["yay", "-Qua"], timeout=60)
        if result:
            aur["count"] = len([l for l in result.splitlines() if l.strip()])
    elif command_exists("paru"):
        aur["available"] = True
        result = run_cmd(["paru", "-Qua"], timeout=60)
        if result:
            aur["count"] = len([l for l in result.splitlines() if l.strip()])
    return aur


def check_pending_updates() -> int:
    result = run_cmd(["pacman", "-Sup", "--print-format", "%n"], timeout=30)
    if result:
        pkgs = [l for l in result.splitlines() if l.strip() and not l.startswith(("http", "ftp"))]
        return len(pkgs)
    return 0


def check_services_pending_restart() -> list[str]:
    services = []
    try:
        result = subprocess.run(
            ["pacman", "-Q", "--check"],
            capture_output=True, text=True, timeout=60,
        )
        for line in result.stderr.splitlines():
            if "useless" in line.lower() or "rebuild" in line.lower() or "update" in line.lower():
                services.append(line.strip())
    except Exception:
        pass

    if Path("/run/reboot-required").exists():
        services.append("Reboot required (update of core libraries)")

    return services


def get_systemd_boot_analysis() -> list[dict]:
    steps = []
    result = run_cmd(["systemd-analyze", "blame"], timeout=15)
    if result:
        for line in result.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                steps.append({"time": parts[0], "unit": parts[1]})
    return steps[:10]


def perform_update(dry_run: bool = False) -> dict:
    info: dict = {
        "pre_update_orphans": [],
        "held_packages": [],
        "partial_upgrades": 0,
        "pending_updates": 0,
        "aur_updates": {"available": False, "count": 0},
        "services_needing_restart": [],
        "update_done": False,
        "errors": [],
        "output": "",
    }

    info["held_packages"] = _pacman_conf_held()
    info["partial_upgrades"] = check_partial_upgrades()
    info["pre_update_orphans"] = check_orphans()
    info["pending_updates"] = check_pending_updates()
    info["aur_updates"] = check_aur_updates()

    if dry_run:
        return info

    try:
        result = subprocess.run(
            ["sudo", "pacman", "-Syu", "--noconfirm"],
            capture_output=True, text=True, timeout=300,
        )
        info["update_done"] = True
        info["output"] = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
        if result.returncode != 0:
            info["errors"].append(result.stderr[-300:] if result.stderr else "Unknown error")
    except subprocess.TimeoutExpired:
        info["errors"].append("Update timed out after 5 minutes")
    except FileNotFoundError:
        info["errors"].append("sudo not available")
    except Exception as e:
        info["errors"].append(str(e))

    info["services_needing_restart"] = check_services_pending_restart()

    return info

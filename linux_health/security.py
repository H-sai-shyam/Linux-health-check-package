import subprocess
import pwd
from pathlib import Path

from linux_health.utils import run_cmd, command_exists


def get_failed_ssh_attempts() -> int:
    try:
        result = subprocess.run(
            ["journalctl", "-u", "sshd", "--since", "30 days ago", "--output=cat"],
            capture_output=True, text=True, timeout=30,
        )
        count = 0
        for line in result.stdout.splitlines():
            if "Failed password" in line:
                count += 1
        return count
    except Exception:
        return -1


def get_open_ports_local() -> list[dict]:
    ports = []
    result = run_cmd(["ss", "-tlnp"], timeout=10)
    if result:
        for line in result.splitlines():
            if "LISTEN" in line:
                parts = line.split()
                if len(parts) >= 4:
                    addr = parts[3] if len(parts) > 3 else parts[-1]
                    port = addr.rsplit(":", 1)[-1] if ":" in addr else addr
                    proc = parts[-1] if len(parts) > 4 else ""
                    if port.isdigit():
                        ports.append({"port": int(port), "address": addr, "process": proc})
    return ports


def check_suid_files() -> list[dict]:
    results = []
    try:
        result = subprocess.run(
            ["find", "/", "-perm", "-4000", "-type", "f", "-not", "-user", "root"],
            capture_output=True, text=True, timeout=30,
        )
        for path in result.stdout.strip().splitlines():
            if path:
                results.append({"path": path, "issue": "SUID file not owned by root"})
    except Exception:
        pass
    return results


def check_world_writable() -> list[str]:
    results = []
    try:
        result = subprocess.run(
            ["find", "/etc", "-perm", "-o=w", "-type", "f"],
            capture_output=True, text=True, timeout=15,
        )
        for path in result.stdout.strip().splitlines():
            if path:
                results.append(path)
    except Exception:
        pass
    return results


def check_uid_zero() -> list[str]:
    users = []
    try:
        for p in pwd.getpwall():
            if p.pw_uid == 0 and p.pw_name != "root":
                users.append(p.pw_name)
    except Exception:
        pass
    return users


def check_recent_timers() -> list[dict]:
    results = []
    try:
        result = subprocess.run(
            ["find",
             str(Path.home() / ".config/systemd"),
             "/etc/systemd/system",
             "/usr/lib/systemd/system",
             "-name", "*.timer", "-mtime", "-7"],
            capture_output=True, text=True, timeout=15,
        )
        for path in result.stdout.strip().splitlines():
            if path:
                results.append({"path": path, "type": "timer"})
    except Exception:
        pass
    return results


def check_recent_cron() -> list[str]:
    results = []
    for cron_path in ["/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly",
                       "/etc/cron.weekly", "/etc/cron.monthly"]:
        path = Path(cron_path)
        if path.exists():
            try:
                result = subprocess.run(
                    ["find", str(path), "-type", "f", "-mtime", "-7"],
                    capture_output=True, text=True, timeout=10,
                )
                for f in result.stdout.strip().splitlines():
                    if f:
                        results.append(f)
            except Exception:
                pass
    return results


def check_arch_audit() -> list[str]:
    if not command_exists("arch-audit"):
        return []
    try:
        result = subprocess.run(
            ["arch-audit", "-q"],
            capture_output=True, text=True, timeout=60,
        )
        pkgs = [l for l in result.stdout.strip().splitlines() if l.strip()]
        return pkgs[:20]
    except Exception:
        return []


def check_kernel_module_security() -> dict:
    info: dict = {}
    try:
        usbguard = command_exists("usbguard")
        info["usbguard"] = usbguard
    except Exception:
        pass
    return info


def collect_all() -> dict:
    data = {
        "failed_ssh_attempts": get_failed_ssh_attempts(),
        "open_ports": get_open_ports_local(),
        "suid_issues": check_suid_files(),
        "world_writable_etc": check_world_writable(),
        "uid_zero_users": check_uid_zero(),
        "recent_timers": check_recent_timers(),
        "recent_cron": check_recent_cron(),
        "known_vulnerable": check_arch_audit(),
        "hostname": run_cmd(["hostname"]) or "",
    }
    return data

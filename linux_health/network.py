import subprocess

from linux_health.utils import run_cmd


def get_info() -> dict:
    info: dict = {
        "connected": False,
        "ip": None,
        "interface": None,
    }

    hostname = run_cmd(["hostname"])
    if hostname:
        info["hostname"] = hostname

    result = run_cmd(["ip", "-4", "addr", "show", "scope", "global"])
    if result:
        for line in result.splitlines():
            parts = line.strip().split()
            if parts and parts[0] == "inet":
                info["ip"] = parts[1].split("/")[0]
                info["connected"] = True
            elif ":" in line and not line.startswith(" "):
                info["interface"] = line.strip().rstrip(":")

    if not info.get("ip"):
        try:
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                if ips:
                    info["ip"] = ips[0]
                    info["connected"] = True
        except Exception:
            pass

    return info

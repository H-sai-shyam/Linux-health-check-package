import subprocess
import socket
from pathlib import Path

from linux_health.utils import run_cmd, command_exists


def get_interfaces() -> list[dict]:
    interfaces = []
    try:
        result = subprocess.run(
            ["ip", "-o", "addr", "show"],
            capture_output=True, text=True, timeout=10,
        )
        ifaces = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                name = parts[1].rstrip(":")
                addr = parts[3]
                if name not in ifaces:
                    ifaces[name] = {"name": name, "ips": []}
                iface = ifaces[name]
                if "/" in addr:
                    iface["ips"].append(addr)

        for name, iface in ifaces.items():
            if name == "lo":
                continue
            link = run_cmd(["ip", "-o", "link", "show", "dev", name], timeout=5)
            state = "down"
            mac = "N/A"
            if link:
                link_parts = link.split()
                if len(link_parts) >= 9:
                    state = link_parts[8]
                    mac = link_parts[1]
            speed = run_cmd(["cat", f"/sys/class/net/{name}/speed"], timeout=3)
            duplex = run_cmd(["cat", f"/sys/class/net/{name}/duplex"], timeout=3)
            iface["state"] = state
            iface["mac"] = mac
            if speed:
                iface["speed"] = f"{speed} Mbps"
            if duplex:
                iface["duplex"] = duplex
            interfaces.append(iface)
    except Exception:
        pass
    return interfaces


def get_gateway() -> str | None:
    result = run_cmd(["ip", "route", "show", "default"], timeout=5)
    if result:
        parts = result.split()
        if len(parts) >= 3:
            return parts[2]
    return None


def get_dns() -> list[str]:
    dns_servers = []
    try:
        for f in ["/etc/resolv.conf"]:
            path = Path(f)
            if path.exists():
                for line in path.read_text().splitlines():
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2:
                            dns_servers.append(parts[1])
    except Exception:
        pass
    try:
        result = run_cmd(["resolvectl", "dns"], timeout=5)
        if result:
            for line in result.splitlines():
                if ":" in line:
                    parts = line.split(":", 1)
                    val = parts[1].strip()
                    if val and val != "_link":
                        dns_servers.append(val)
    except Exception:
        pass
    return dns_servers


def ping_test(target: str = "1.1.1.1", count: int = 3) -> dict:
    result: dict = {"target": target, "reachable": False, "avg_ms": None, "loss": 100}
    try:
        r = subprocess.run(
            ["ping", "-c", str(count), "-W", "3", target],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            result["reachable"] = True
            for line in r.stdout.splitlines():
                if "avg" in line:
                    try:
                        avg = line.split("/")[4]
                        result["avg_ms"] = float(avg)
                    except (IndexError, ValueError):
                        pass
                if "packet loss" in line:
                    try:
                        loss = line.split(",")[2].strip().split()[0].rstrip("%")
                        result["loss"] = float(loss)
                    except (IndexError, ValueError):
                        pass
    except Exception:
        pass
    return result


def dns_resolve(hostname: str = "google.com") -> dict:
    result: dict = {"hostname": hostname, "ips": [], "time_ms": None}
    try:
        import time
        start = time.time()
        addrs = socket.getaddrinfo(hostname, 80)
        elapsed = (time.time() - start) * 1000
        result["time_ms"] = round(elapsed, 1)
        result["ips"] = list(set(a[4][0] for a in addrs))
    except Exception:
        pass
    return result


def get_listening_ports() -> list[dict]:
    ports = []
    result = run_cmd(["ss", "-tlnp"], timeout=10)
    if result:
        for line in result.splitlines():
            if "LISTEN" in line:
                parts = line.split()
                if len(parts) >= 5:
                    addr = parts[4]
                    proc = parts[5] if len(parts) > 5 else ""
                    port = addr.rsplit(":", 1)[-1] if ":" in addr else addr
                    ports.append({"address": addr, "port": port, "process": proc})
    return ports


def get_active_connections() -> int:
    result = run_cmd(["ss", "-tn", "state", "established"], timeout=10)
    if result:
        lines = [l for l in result.splitlines() if l.strip() and not l.startswith("State")]
        return len(lines)
    return 0


def get_wifi_info() -> dict:
    info: dict = {"present": False}
    if not command_exists("iw"):
        return info
    iface = run_cmd(["iw", "dev"], timeout=5)
    if not iface:
        return info
    for line in iface.splitlines():
        if "Interface" in line:
            name = line.split()[-1]
            link = run_cmd(["iw", "dev", name, "link"], timeout=5)
            if link:
                info["present"] = True
                info["interface"] = name
                for l in link.splitlines():
                    l = l.strip()
                    if "SSID" in l:
                        info["ssid"] = l.split("SSID:")[-1].strip()
                    elif "signal" in l:
                        try:
                            info["signal_dbm"] = int(l.split()[1])
                        except (IndexError, ValueError):
                            pass
                    elif "freq" in l:
                        try:
                            info["freq_mhz"] = int(l.split()[1])
                        except (IndexError, ValueError):
                            pass
                    elif "tx bitrate" in l:
                        try:
                            info["bitrate"] = l.split("bitrate:")[-1].strip()
                        except IndexError:
                            pass
    if info.get("signal_dbm") is not None:
        sig = info["signal_dbm"]
        if sig >= -50:
            info["signal_quality"] = "Excellent"
        elif sig >= -60:
            info["signal_quality"] = "Good"
        elif sig >= -70:
            info["signal_quality"] = "Fair"
        else:
            info["signal_quality"] = "Weak"
    return info


def get_public_ip() -> str | None:
    return run_cmd(["curl", "-s", "https://ifconfig.me", "--max-time", "5"], timeout=10)


def collect_all() -> dict:
    interfaces = get_interfaces()
    gateway = get_gateway()
    dns = get_dns()
    ping_cloudflare = ping_test("1.1.1.1")
    ping_google = ping_test("8.8.8.8")
    resolve = dns_resolve("google.com")
    ports = get_listening_ports()
    active_conns = get_active_connections()
    wifi = get_wifi_info()
    public_ip = get_public_ip()

    data = {
        "hostname": socket.gethostname(),
        "interfaces": interfaces,
        "gateway": gateway,
        "dns_servers": dns,
        "ping_cloudflare": ping_cloudflare,
        "ping_google": ping_google,
        "dns_resolve": resolve,
        "listening_ports": ports,
        "active_connections": active_conns,
        "wifi": wifi,
        "public_ip": public_ip,
    }
    return data

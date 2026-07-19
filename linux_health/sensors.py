import subprocess
from pathlib import Path

from linux_health.utils import run_cmd, command_exists


def _read_sys_int(path: str) -> int | None:
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError, FileNotFoundError):
        return None


def get_cpu_temps_per_core() -> list[dict]:
    cores = []
    base = Path("/sys/class/thermal")
    if not base.exists():
        return cores
    for zone in sorted(base.glob("thermal_zone*")):
        try:
            typ = (zone / "type").read_text().strip()
            temp = int((zone / "temp").read_text().strip()) / 1000
            if "x86" in typ or "cpu" in typ or "core" in typ or "pkg" in typ:
                cores.append({"type": typ, "temp": temp})
        except (OSError, ValueError):
            pass
    if not cores:
        result = run_cmd(["sensors", "-u"], timeout=10)
        if result:
            current_core = ""
            for line in result.splitlines():
                if line.startswith("Package id") or line.startswith("Core"):
                    current_core = line.split(":")[0].strip()
                if "temp1_input" in line:
                    try:
                        val = float(line.split()[1])
                        cores.append({"type": current_core or "unknown", "temp": val / 1000 if val > 100 else val})
                    except (ValueError, IndexError):
                        pass
    return cores


def get_fan_speeds() -> list[dict]:
    fans = []
    base = Path("/sys/class/hwmon")
    if base.exists():
        for hwmon in sorted(base.glob("hwmon*")):
            for fan_input in sorted(hwmon.glob("fan*_input")):
                try:
                    speed = int(fan_input.read_text().strip())
                    label_file = fan_input.with_name(fan_input.name.replace("_input", "_label"))
                    label = label_file.read_text().strip() if label_file.exists() else fan_input.name
                    fans.append({"label": label, "speed_rpm": speed})
                except (OSError, ValueError):
                    pass

    if not fans and command_exists("sensors"):
        result = run_cmd(["sensors"], timeout=10)
        if result:
            for line in result.splitlines():
                if "RPM" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        label = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        try:
                            fans.append({"label": label, "speed_rpm": int(val)})
                        except ValueError:
                            pass
    return fans


def get_gpu_info() -> list[dict]:
    gpus = []
    if command_exists("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,utilization.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    gpu = {
                        "vendor": "NVIDIA",
                        "name": parts[1] if len(parts) > 1 else "",
                        "temp": float(parts[2]) if parts[2] else None,
                        "usage": float(parts[3]) if len(parts) > 3 and parts[3] else None,
                    }
                    if len(parts) > 4 and parts[4]:
                        gpu["power_w"] = float(parts[4])
                    gpus.append(gpu)
        except Exception:
            pass

    for drm in Path("/sys/class/drm").glob("card*"):
        if (drm / "device").exists():
            try:
                vendor = (drm / "device" / "vendor").read_text().strip()
                if vendor == "0x1002" or vendor == "0x8086":
                    temp_path = drm / "device" / "hwmon"
                    if temp_path.exists():
                        for hwmon in temp_path.glob("hwmon*"):
                            temp = _read_sys_int(str(hwmon / "temp1_input"))
                            if temp:
                                exists = any(g.get("temp") == temp / 1000 for g in gpus)
                                if not exists:
                                    gpus.append({
                                        "vendor": "AMD" if vendor == "0x1002" else "Intel",
                                        "name": drm.name,
                                        "temp": temp / 1000,
                                    })
            except (OSError, FileNotFoundError):
                pass
    return gpus


def get_disk_temps() -> list[dict]:
    disks = []
    base = Path("/sys/class/nvme")
    if base.exists():
        for nvme in base.glob("nvme*"):
            try:
                temp = _read_sys_int(str(nvme / "device" / "temp"))
                if temp:
                    disks.append({
                        "device": nvme.name,
                        "temp": temp - 273 if temp > 200 else temp,
                        "type": "NVMe",
                    })
            except (OSError, ValueError):
                pass

    if command_exists("nvme"):
        try:
            result = subprocess.run(
                ["sudo", "nvme", "list", "--output-format=json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                for device in data.get("Devices", []):
                    disks.append({
                        "device": device.get("DevicePath", ""),
                        "temp": device.get("Temperature", 0),
                        "type": "NVMe",
                    })
        except Exception:
            pass

    if command_exists("smartctl"):
        try:
            result = subprocess.run(
                ["sudo", "smartctl", "--scan"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                if "nvme" in line.lower():
                    continue
                parts = line.split()
                if parts:
                    dev = parts[0]
                    temp_result = subprocess.run(
                        ["sudo", "smartctl", "-A", dev, "--json"],
                        capture_output=True, text=True, timeout=15,
                    )
                    if temp_result.returncode == 0:
                        import json
                        data = json.loads(temp_result.stdout)
                        temp = data.get("temperature", {}).get("current")
                        if temp:
                            disks.append({
                                "device": dev,
                                "temp": temp,
                                "type": "HDD/SSD",
                            })
        except Exception:
            pass
    return disks


def get_battery_temp() -> float | None:
    base = Path("/sys/class/power_supply")
    if not base.exists():
        return None
    for bat in base.glob("BAT*"):
        try:
            temp = (bat / "temp").read_text().strip()
            return int(temp) / 10
        except (OSError, ValueError, FileNotFoundError):
            pass
    return None


def get_power_consumption() -> list[dict]:
    readings = []
    supported = Path("/sys/class/powercap")
    if supported.exists():
        for domain in sorted(supported.glob("*")):
            try:
                name = (domain / "name").read_text().strip()
                energy = _read_sys_int(str(domain / "energy_uj"))
                max_range = _read_sys_int(str(domain / "energy_uj_max"))
                if energy and max_range:
                    readings.append({"domain": name, "energy_uj": energy, "max_uj": max_range})
            except (OSError, FileNotFoundError):
                pass

    if command_exists("powertop") and not readings:
        try:
            result = subprocess.run(
                ["sudo", "powertop", "--csv=/dev/stdout", "--iterations=1"],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.splitlines():
                if "The system baseline power estimate" in line:
                    readings.append({"domain": "total", "estimate": line.strip()})
        except Exception:
            pass

    return readings


def get_soc_temp() -> float | None:
    try:
        result = subprocess.run(
            ["cat", "/sys/class/thermal/thermal_zone*/temp"],
            capture_output=True, text=True, timeout=5, shell=True,
        )
        for val in result.stdout.strip().splitlines():
            v = val.strip()
            if v:
                temp = int(v) / 1000
                if 10 < temp < 120:
                    return temp
    except Exception:
        pass
    return None


def collect_all() -> dict:
    data = {
        "cpu_temps": get_cpu_temps_per_core(),
        "gpus": get_gpu_info(),
        "fans": get_fan_speeds(),
        "disk_temps": get_disk_temps(),
        "battery_temp": get_battery_temp(),
        "power": get_power_consumption(),
    }
    return data

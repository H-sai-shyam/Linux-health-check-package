import subprocess
from pathlib import Path

from linux_health.collectors.base import BaseCollector, Finding
from linux_health.utils import run_cmd, command_exists


def _read_sys_str(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except (OSError, FileNotFoundError):
        return None


def temp_to_condition(temp: float) -> float:
    if temp < 60:
        return 100.0
    if temp < 75:
        return 80.0
    if temp < 85:
        return 50.0
    if temp < 95:
        return 25.0
    return 10.0


def _sys_name(path: Path) -> str:
    name_file = path / "device" / "name"
    if name_file.exists():
        try:
            return name_file.read_text().strip()
        except OSError:
            pass
    product = path / "device" / "product"
    if product.exists():
        try:
            return product.read_text().strip()
        except OSError:
            pass
    return path.name


class HardwareScannerCollector(BaseCollector):
    name = "hardware"
    tier = "standard"

    def collect(self) -> list[Finding]:
        findings: list[Finding] = []

        findings.extend(self._scan_input_devices())
        findings.extend(self._scan_power_supplies())
        findings.extend(self._scan_thermal())
        findings.extend(self._scan_fans())
        findings.extend(self._scan_gpus())
        findings.extend(self._scan_usb_controllers())

        return findings

    def _scan_input_devices(self) -> list[Finding]:
        findings = []
        input_dir = Path("/sys/class/input")
        if not input_dir.exists():
            return findings

        seen = set()
        for event_dev in sorted(input_dir.glob("event*")):
            try:
                name = _sys_name(event_dev)
                if not name or name in seen:
                    continue
                seen.add(name)

                dev_path = event_dev.resolve()
                phys = _read_sys_str(str(event_dev / "device" / "phys")) or ""

                cond = 100.0
                if "keyboard" in name.lower():
                    dev_type = "Keyboard"
                    cond = 100.0
                elif "touchpad" in name.lower() or "trackpoint" in name.lower() or "trackpad" in name.lower():
                    dev_type = "Touchpad"
                    irq_check = self._check_touchpad_irq()
                    if irq_check is not None:
                        cond = irq_check
                    else:
                        cond = 100.0
                elif "mouse" in name.lower() or "pointer" in name.lower():
                    dev_type = "Mouse"
                    cond = 100.0
                elif "camera" in name.lower() or "video" in name.lower():
                    dev_type = "Camera"
                    cond = 100.0
                elif "tablet" in name.lower():
                    dev_type = "Tablet"
                    cond = 100.0
                elif "lid" in name.lower():
                    dev_type = "Lid Switch"
                    cond = 100.0
                elif "power" in name.lower() and "button" in name.lower():
                    dev_type = "Power Button"
                    cond = 100.0
                else:
                    if phys.startswith("usb"):
                        dev_type = "USB Input"
                    else:
                        dev_type = "Input Device"

                bar = self._cond_bar(cond)
                status = self._cond_text(cond)
                findings.append(Finding(
                    module="hardware.input",
                    title=f"{dev_type}: {name[:50]}",
                    detail=f"{dev_type} — Condition: {bar}  {cond:.0f}% ({status})",
                    severity=self._cond_severity(cond),
                    evidence={"type": dev_type, "device": name, "condition_pct": cond, "event": event_dev.name},
                    suggestion="" if cond >= 80 else "Check device connection or driver status.",
                ))
            except (OSError, FileNotFoundError):
                pass

        return findings

    def _check_touchpad_irq(self) -> float | None:
        try:
            result = subprocess.run(
                ["grep", "ELAN", "/proc/interrupts"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                parts = result.stdout.strip().split()
                if len(parts) > 1:
                    irqs = [int(p) for p in parts[1:-1] if p.isdigit()]
                    total = sum(irqs)
                    max_single = max(irqs) if irqs else 0
                    if total > 0:
                        spread = 1.0 - (max_single / total) * (len(irqs) - 1)
                        return max(10, min(100, spread * 100))
        except Exception:
            pass
        return None

    def _scan_power_supplies(self) -> list[Finding]:
        findings = []
        ps_dir = Path("/sys/class/power_supply")
        if not ps_dir.exists():
            return findings

        for supply in sorted(ps_dir.iterdir()):
            try:
                name = supply.name
                stype = _read_sys_str(str(supply / "type")) or "Unknown"
                online = _read_sys_str(str(supply / "online"))
                status = _read_sys_str(str(supply / "status")) or "Unknown"

                if stype == "Mains":
                    cond = 100.0 if online == "1" else 0.0
                    bar = self._cond_bar(cond)
                    findings.append(Finding(
                        module="hardware.power",
                        title=f"Charger: {name}",
                        detail=f"AC Adapter — Condition: {bar}  {cond:.0f}% ({'Online' if cond == 100 else 'Disconnected'})",
                        severity=self._cond_severity(cond),
                        evidence={"type": "AC Adapter", "online": online, "condition_pct": cond},
                        suggestion="" if cond == 100 else "Connect the charger.",
                    ))

                elif stype == "Battery":
                    cap_str = _read_sys_str(str(supply / "capacity"))
                    cap = int(cap_str) if cap_str else None
                    health_str = _read_sys_str(str(supply / "health")) or "Unknown"
                    if cap is not None:
                        cond = float(cap)
                    else:
                        cond = 100.0
                    bar = self._cond_bar(cond)
                    findings.append(Finding(
                        module="hardware.power",
                        title=f"Battery: {name}",
                        detail=f"Battery — Level: {cap}%  Status: {status}  Health: {health_str}",
                        severity=self._cond_severity(cond),
                        evidence={"type": "Battery", "capacity_pct": cap, "status": status, "health": health_str, "condition_pct": cond},
                        suggestion="" if cond >= 20 else "Battery level critically low. Charge immediately.",
                    ))

            except (OSError, FileNotFoundError):
                pass

        return findings

    def _scan_thermal(self) -> list[Finding]:
        findings = []
        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            try:
                typ = _read_sys_str(str(zone / "type")) or "unknown"
                temp_str = _read_sys_str(str(zone / "temp"))
                if temp_str:
                    temp = int(temp_str) / 1000
                    cond = temp_to_condition(temp)
                    bar = self._cond_bar(cond)
                    findings.append(Finding(
                        module="hardware.thermal",
                        title=f"Temperature: {typ}",
                        detail=f"{typ} — {temp:.1f}°C  Condition: {bar}  {cond:.0f}%",
                        severity=self._cond_severity(cond),
                        evidence={"sensor": typ, "temperature": temp, "condition_pct": cond},
                        suggestion="" if temp < 85 else "High temperature detected. Check cooling system.",
                    ))
            except (OSError, FileNotFoundError, ValueError):
                pass
        return findings

    def _scan_fans(self) -> list[Finding]:
        findings = []
        hwmon_dir = Path("/sys/class/hwmon")
        if hwmon_dir.exists():
            for hwmon in sorted(hwmon_dir.glob("hwmon*")):
                for fan_input in sorted(hwmon.glob("fan*_input")):
                    try:
                        speed = int(fan_input.read_text().strip())
                        label_file = fan_input.with_name(fan_input.name.replace("_input", "_label"))
                        label = label_file.read_text().strip() if label_file.exists() else fan_input.name
                        if speed > 0:
                            cond = 100.0 if speed > 500 else 80.0
                        else:
                            cond = 50.0
                        bar = self._cond_bar(cond)
                        findings.append(Finding(
                            module="hardware.fan",
                            title=f"Fan: {label}",
                            detail=f"{label} — {speed} RPM  Condition: {bar}  {cond:.0f}%",
                            severity=self._cond_severity(cond),
                            evidence={"fan": label, "rpm": speed, "condition_pct": cond},
                            suggestion="" if speed > 0 else "Fan not spinning. Check connection or cooling system.",
                        ))
                    except (OSError, ValueError):
                        pass

        if not findings:
            result = run_cmd(["sensors"], timeout=10)
            if result:
                for line in result.splitlines():
                    if "RPM" in line:
                        parts = line.split(":")
                        if len(parts) == 2:
                            label = parts[0].strip()
                            try:
                                rpm = int(parts[1].strip().split()[0])
                                cond = 100.0 if rpm > 500 else 80.0 if rpm > 0 else 50.0
                                bar = self._cond_bar(cond)
                                findings.append(Finding(
                                    module="hardware.fan",
                                    title=f"Fan: {label}",
                                    detail=f"{label} — {rpm} RPM  Condition: {bar}  {cond:.0f}%",
                                    severity=self._cond_severity(cond),
                                    evidence={"fan": label, "rpm": rpm, "condition_pct": cond},
                                ))
                            except (ValueError, IndexError):
                                pass
        return findings

    def _scan_gpus(self) -> list[Finding]:
        findings = []
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
                        name = parts[1] if len(parts) > 1 else "NVIDIA GPU"
                        temp_str = parts[2]
                        try:
                            temp = float(temp_str)
                            cond = temp_to_condition(temp)
                            usage = parts[3] if len(parts) > 3 else "?"
                            power = parts[4] if len(parts) > 4 and parts[4] else "?"
                            bar = self._cond_bar(cond)
                            detail = f"{name} — {temp:.0f}°C  Usage: {usage}%  Power: {power}W"
                            if temp < 60:
                                detail += f"  Condition: {bar}  {cond:.0f}%"
                            else:
                                detail += f"  Condition: {bar}  {cond:.0f}% (warm)"
                            findings.append(Finding(
                                module="hardware.gpu",
                                title=f"GPU: {name[:40]}",
                                detail=detail,
                                severity=self._cond_severity(cond),
                                evidence={"gpu": name, "temp": temp, "usage": usage, "condition_pct": cond},
                            ))
                        except (ValueError, IndexError):
                            pass
            except Exception:
                pass

        for drm in Path("/sys/class/drm").glob("card*"):
            if (drm / "device").exists():
                try:
                    vendor = Path(drm / "device" / "vendor").read_text().strip()
                    name = _sys_name(drm)
                    if "0x1002" in vendor or "0x8086" in vendor:
                        temp_path = drm / "device" / "hwmon"
                        if temp_path.exists():
                            for hwmon in temp_path.glob("hwmon*"):
                                temp_str = _read_sys_str(str(hwmon / "temp1_input"))
                                if temp_str:
                                    temp = int(temp_str) / 1000
                                    cond = temp_to_condition(temp)
                                    bar = self._cond_bar(cond)
                                    findings.append(Finding(
                                        module="hardware.gpu",
                                        title=f"GPU: {name[:35]}",
                                        detail=f"{name[:35]} — {temp:.0f}°C  Condition: {bar}  {cond:.0f}%",
                                        severity=self._cond_severity(cond),
                                        evidence={"gpu": name, "temp": temp, "condition_pct": cond},
                                    ))
                except (OSError, FileNotFoundError):
                    pass
        return findings

    def _scan_usb_controllers(self) -> list[Finding]:
        findings = []
        usb_dir = Path("/sys/bus/usb/devices")
        if not usb_dir.exists():
            return findings

        controllers_seen = set()
        for dev in sorted(usb_dir.iterdir()):
            try:
                if "-" not in dev.name and "usb" not in dev.name:
                    continue
                speed = _read_sys_str(str(dev / "speed"))
                product = _read_sys_str(str(dev / "product"))
                manufacturer = _read_sys_str(str(dev / "manufacturer"))
                b_max_power = _read_sys_str(str(dev / "bMaxPower"))

                if not product and not manufacturer:
                    continue

                key = product or manufacturer or dev.name
                if key in controllers_seen:
                    continue
                controllers_seen.add(key)

                cond = 100.0
                dev_type = "USB Device"
                name = (manufacturer or "") + (" " if manufacturer and product else "") + (product or "")
                name = name.strip() or dev.name

                if speed:
                    speed_mbps = int(speed)
                    if speed_mbps >= 5000:
                        cond = 100.0
                    elif speed_mbps >= 480:
                        cond = 85.0
                    elif speed_mbps >= 12:
                        cond = 70.0
                    else:
                        cond = 60.0

                if not name:
                    continue

                bar = self._cond_bar(cond)
                detail = f"{name[:50]}  Speed: {speed} Mbps" if speed else name[:50]
                detail += f"  {b_max_power}" if b_max_power else ""
                detail += f"  Condition: {bar}  {cond:.0f}%"

                findings.append(Finding(
                    module="hardware.usb",
                    title=f"{dev_type}: {name[:40]}",
                    detail=detail,
                    severity=self._cond_severity(cond),
                    evidence={"usb_device": name, "speed": speed, "condition_pct": cond},
                ))
            except (OSError, ValueError):
                pass

        return findings

    def _cond_bar(self, pct: float, w: int = 8) -> str:
        filled = int((pct / 100) * w)
        return "█" * filled + "░" * (w - filled)

    def _cond_text(self, pct: float) -> str:
        if pct >= 90:
            return "Excellent"
        if pct >= 70:
            return "Good"
        if pct >= 50:
            return "Fair"
        if pct >= 25:
            return "Poor"
        return "Critical"

    def _cond_severity(self, pct: float) -> str:
        if pct >= 80:
            return "pass"
        if pct >= 50:
            return "info"
        if pct >= 25:
            return "warning"
        return "critical"

from pathlib import Path

BATTERY_PATH = "/sys/class/power_supply"


def _read_int(path: Path, name: str) -> int | None:
    try:
        return int((path / name).read_text().strip())
    except (OSError, ValueError, FileNotFoundError):
        return None


def _read_str(path: Path, name: str) -> str | None:
    try:
        val = (path / name).read_text().strip()
        return val if val else None
    except (OSError, FileNotFoundError):
        return None


def _find_battery() -> Path | None:
    bat_path = Path(BATTERY_PATH)
    if not bat_path.exists():
        return None
    bats = [d for d in bat_path.iterdir() if d.name.startswith("BAT")]
    return bats[0] if bats else None


def fmt_duration(hours: float) -> str:
    if hours <= 0:
        return "Calculating..."
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def get_info() -> dict:
    info: dict = {"present": False}
    bat = _find_battery()
    if not bat:
        return info

    info["present"] = True
    info["path"] = str(bat)

    info["capacity"] = _read_int(bat, "capacity")
    if info["capacity"] is not None:
        info["capacity_h"] = f"{info['capacity']}%"

    info["status"] = _read_str(bat, "status")
    info["technology"] = _read_str(bat, "technology")
    info["manufacturer"] = _read_str(bat, "manufacturer")
    info["model_name"] = _read_str(bat, "model_name")
    info["serial_number"] = _read_str(bat, "serial_number")
    info["capacity_level"] = _read_str(bat, "capacity_level")

    temp_raw = _read_int(bat, "temp")
    if temp_raw is not None:
        info["temperature"] = round(temp_raw / 10, 1)

    info["cycle_count"] = _read_int(bat, "cycle_count")

    charge_full = _read_int(bat, "charge_full")
    charge_full_design = _read_int(bat, "charge_full_design")
    charge_now = _read_int(bat, "charge_now")

    energy_full = _read_int(bat, "energy_full")
    energy_full_design = _read_int(bat, "energy_full_design")
    energy_now = _read_int(bat, "energy_now")

    voltage_now = _read_int(bat, "voltage_now")
    current_now = _read_int(bat, "current_now")
    power_now = _read_int(bat, "power_now")

    voltage_min_design = _read_int(bat, "voltage_min_design")

    info["voltage_now"] = voltage_now
    if voltage_now is not None:
        info["voltage_now_h"] = f"{voltage_now / 1_000_000:.3f}V"

    if voltage_min_design is not None:
        info["voltage_min_design_h"] = f"{voltage_min_design / 1_000_000:.3f}V"

    if current_now is not None:
        cur_ma = current_now / 1000
        info["current_now_h"] = f"{abs(cur_ma):.0f}mA {'discharge' if cur_ma < 0 else 'charge'}"

    if power_now is not None:
        info["power_now_h"] = f"{power_now / 1_000_000:.2f}W"

    if charge_full is not None and charge_full_design is not None and charge_full_design > 0:
        info["health"] = round((charge_full / charge_full_design) * 100, 1)
        info["health_h"] = f"{info['health']}%"
        info["degradation"] = round(100 - info["health"], 1)
        info["degradation_h"] = f"{info['degradation']}%"
        lost_ah = (charge_full_design - charge_full) / 1_000_000
        info["capacity_lost_h"] = f"{lost_ah * 1000:.0f}mAh" if lost_ah < 1 else f"{lost_ah:.1f}Ah"
        info["charge_full_design_h"] = f"{charge_full_design / 1000:.0f}mAh"
        info["charge_full_h"] = f"{charge_full / 1000:.0f}mAh"
    elif energy_full is not None and energy_full_design is not None and energy_full_design > 0:
        info["health"] = round((energy_full / energy_full_design) * 100, 1)
        info["health_h"] = f"{info['health']}%"
        info["degradation"] = round(100 - info["health"], 1)
        info["degradation_h"] = f"{info['degradation']}%"
        lost_wh = (energy_full_design - energy_full) / 1_000_000
        info["capacity_lost_h"] = f"{lost_wh:.1f}Wh"
        info["charge_full_design_h"] = f"{energy_full_design / 1_000_000:.1f}Wh"
        info["charge_full_h"] = f"{energy_full / 1_000_000:.1f}Wh"
    else:
        if charge_full is not None:
            info["charge_full_h"] = f"{charge_full / 1000:.0f}mAh"
        if charge_full_design is not None:
            info["charge_full_design_h"] = f"{charge_full_design / 1000:.0f}mAh"

    if charge_now is not None:
        info["charge_now_h"] = f"{charge_now / 1000:.0f}mAh"
    elif energy_now is not None:
        info["charge_now_h"] = f"{energy_now / 1_000_000:.1f}Wh"

    if charge_now is not None and charge_full is not None and charge_full > 0:
        info["charge_percent"] = round((charge_now / charge_full) * 100, 1)
    elif energy_now is not None and energy_full is not None and energy_full > 0:
        info["charge_percent"] = round((energy_now / energy_full) * 100, 1)

    if info.get("capacity") is not None and info.get("charge_percent") is None:
        info["charge_percent"] = info["capacity"]

    status = info.get("status", "")
    if status == "Discharging" and power_now is not None and power_now > 0 and energy_now is not None:
        hours = energy_now / power_now
        info["time_remaining"] = hours
        info["time_remaining_h"] = fmt_duration(hours)
        info["time_remaining_label"] = "Remaining"
    elif status == "Charging" and power_now is not None and power_now > 0:
        if energy_now is not None and energy_full is not None:
            hours = (energy_full - energy_now) / power_now
            info["time_remaining"] = hours
            info["time_remaining_h"] = fmt_duration(hours)
            info["time_remaining_label"] = "Until full"
        elif charge_now is not None and charge_full is not None:
            hours = (charge_full - charge_now) / (power_now / (voltage_now / 1_000_000 if voltage_now else 3.7))
            info["time_remaining"] = hours
            info["time_remaining_h"] = fmt_duration(hours)
            info["time_remaining_label"] = "Until full"
    elif status == "Full":
        pass
    elif status == "Charging":
        info["time_remaining_h"] = "Calculating..."
        info["time_remaining_label"] = "Time"

    if current_now is not None and current_now != 0 and voltage_now is not None:
        power_w = (abs(current_now) * voltage_now) / 1e12
        info["power_now_derived_h"] = f"{power_w:.2f}W"

    return info


def get_degradation_history() -> dict:
    info = get_info()
    bat = _find_battery()
    if not bat:
        return {"available": False}

    charge_full_design = _read_int(bat, "charge_full_design")
    charge_full = _read_int(bat, "charge_full")
    energy_full_design = _read_int(bat, "energy_full_design")
    energy_full = _read_int(bat, "energy_full")

    if charge_full_design is not None and charge_full is not None:
        lost_raw = charge_full_design - charge_full
        pct = round((charge_full / charge_full_design) * 100, 1) if charge_full_design > 0 else 0
        return {
            "available": True,
            "design_capacity": charge_full_design,
            "design_capacity_h": f"{charge_full_design / 1000:.0f}mAh",
            "current_capacity": charge_full,
            "current_capacity_h": f"{charge_full / 1000:.0f}mAh",
            "lost_capacity": lost_raw,
            "lost_capacity_h": f"{lost_raw / 1000:.0f}mAh",
            "health_pct": pct,
            "degradation_pct": round(100 - pct, 1),
        }
    elif energy_full_design is not None and energy_full is not None:
        lost_raw = energy_full_design - energy_full
        pct = round((energy_full / energy_full_design) * 100, 1) if energy_full_design > 0 else 0
        return {
            "available": True,
            "design_capacity": energy_full_design,
            "design_capacity_h": f"{energy_full_design / 1_000_000:.1f}Wh",
            "current_capacity": energy_full,
            "current_capacity_h": f"{energy_full / 1_000_000:.1f}Wh",
            "lost_capacity": lost_raw,
            "lost_capacity_h": f"{lost_raw / 1_000_000:.1f}Wh",
            "health_pct": pct,
            "degradation_pct": round(100 - pct, 1),
        }

    return {"available": False}

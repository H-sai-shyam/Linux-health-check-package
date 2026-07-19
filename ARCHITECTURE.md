# Linux Health — Complete Architecture Document

> **Version:** 1.2.0  
> **Location:** `/home/shyam/linux-health/`  
> **Shortcut:** `lh` (symlink to `linux-health`)  
> **Source size:** ~1.6 MB | **Total footprint:** < 50 MB  
> **Dependencies:** `python-rich`, `python-psutil`, `python-typer`

---

## 1. Project Structure

```
/home/shyam/linux-health/
├── linux_health/                    # Python package (20+ modules)
│   ├── __init__.py                  # Package version
│   ├── __main__.py                  # Entry: `python3 -m linux_health`
│   ├── cli.py                       # CLI entry point, flag routing
│   ├── config.py                    # TOML config loader
│   ├── health.py                    # Dashboard data aggregator
│   ├── cpu.py                       # CPU usage & temperature
│   ├── memory.py                    # RAM & swap
│   ├── disk.py                      # Disk usage, large dirs/files, mounts
│   ├── battery.py                   # Battery health, charge, electrical
│   ├── temperature.py               # CPU/GPU temperature (thin wrapper)
│   ├── network.py                   # Basic network (hostname, IP)
│   ├── netdiag.py                   # Full network diagnostics (--net)
│   ├── cleanup.py                   # Cache/thumbnails/tmp/journal cleanup
│   ├── pacman.py                    # Pacman cache cleanup (paccache)
│   ├── flatpak.py                   # Flatpak unused runtime cleanup
│   ├── docker.py                    # Docker prune
│   ├── java.py                      # Maven/Gradle/target/build/node_modules
│   ├── update.py                    # System update checks & execution
│   ├── security.py                  # Security audit
│   ├── boot.py                      # Boot & kernel analysis
│   ├── sensors.py                   # Hardware sensor readout
│   ├── logger.py                    # JSON logging
│   ├── history.py                   # Cleanup history
│   ├── notifications.py             # notify-send integration
│   ├── report.py                    # All rich-formatted output functions
│   ├── utils.py                     # Shared helpers
│   ├── trash.py                     # Rollbackable cleanup system
│   ├── collectors/                  # Collector framework
│   │   ├── __init__.py
│   │   ├── base.py                  # Finding dataclass, BaseCollector ABC
│   │   ├── kernelcheck.py           # Kernel-level analysis (--kernel)
│   │   ├── malware.py               # Malware/rootkit scanner (--malware)
│   │   ├── hardware_scanner.py      # Full hardware inventory with condition %
│   │   └── healthcheck.py           # Orchestrator for default dashboard runs
│   └── engine/                      # NEW: Scoring & runner engine
│       ├── __init__.py
│       ├── runner.py                # Runs collectors with timeout isolation
│       └── scoring.py               # 0-100 health score calculator
├── systemd/                         # Systemd unit files
│   ├── linux-health.service         # Cleanup job
│   ├── linux-health.timer           # Weekly timer
│   └── touchpad-irq-affinity.service # Touchpad IRQ fix (optional)
├── tests/
│   ├── test_config.py
│   └── test_utils.py
├── install.sh                       # Installation script
├── uninstall.sh                     # Uninstallation script
├── pyproject.toml                   # Python build config
├── setup.cfg                        # Package metadata
├── README.md                        # User docs
├── COMMAND-EXPLANATION.md           # Internal workings of every command
├── UPGRADE-PLAN.md                  # Future roadmap
└── ARCHITECTURE.md                  # This file
```

---

## 2. CLI Architecture (`cli.py`)

The CLI uses **Typer** (a modern Click wrapper) with a single `@app.callback` that handles all flags. There are no subcommands — every operation is a boolean flag on the main function.

```
                lh
                 │
           @app.callback()
                 │
          ┌──────┼──────────┬──────────┬──────────┬──────────┬──────────┬──────┐
          │      │          │          │          │          │          │      │
      --help  --version  --history  --disk  --battery  --update  --kernel ...
          │      │          │          │          │          │          │
     show_  console.  show_    show_    show_    show_     KernelCheck_
     help()  print()  history  findings_ battery_  update    Collector()
                       ()      summary  report()  report()      │
                               + disk                engine.scoring()
                               analysis                   │
                                                    show_deep_scan_results()

  --malware  --net  --security --boot --sensors --doctor --clean   (no flag)
      │        │        │        │        │        │        │         │
  Malware_   show_   show_    show_   Hardware_  show_   run_    Dashboard
  Collector  net_    sec_     boot_   Scanner +  doctor  cleanup()  │
      │      report  report   report  sensors    results()       health.
  engine.    ()      ()       ()      report()                  collect_all
  scoring()                         │                               │
      │                        show_findings_                   health_check
  show_deep_                     summary()                     included via
  scan_results()                + sensors                      collectors/
                                 report()                      healthcheck.py
```

### Flag priority (first match wins):
1. `--help` → custom rich help page
2. `--version` → version string
3. `--history` → cleanup history
4. `--disk` → disk analysis + severity findings
5. `--battery` → battery report + severity findings
6. `--update` → system update
7. `--kernel` → deep kernel analysis + severity findings
8. `--malware` → malware/rootkit scan + severity findings
9. `--net` → network diagnostics + severity findings
10. `--security` → security audit
11. `--boot` → boot & kernel analysis + severity findings
12. `--sensors` → hardware inventory with condition % + severity findings
13. `--doctor` → diagnostics
14. `--clean` → run cleanup
15. _(no flag)_ → default dashboard + health score

### Special flag interactions:
- `--clean --dry-run` → preview cleanup without deleting
- `--update --dry-run` → pre-flight checks only, no actual update

---

## 3. Configuration System (`config.py`)

### File location: `~/.config/linux-health/config.toml`

### Default configuration:

| Key | Default | Description |
|---|---|---|
| `auto_cleanup` | `true` | Enable scheduled cleanup |
| `cleanup_interval_days` | `7` | Days between cleanups |
| `notifications` | `true` | Send `notify-send` after cleanup |
| `cleanup_cache` | `true` | Clean user cache |
| `cleanup_pacman` | `true` | Clean pacman cache |
| `cleanup_flatpak` | `true` | Remove unused Flatpak runtimes |
| `cleanup_tmp` | `true` | Clean `/tmp` |
| `cleanup_journal` | `true` | Vacuum journal logs (7d) |
| `cleanup_maven` | `false` | Clean Maven repo |
| `cleanup_gradle` | `false` | Clean Gradle cache |
| `cleanup_docker` | `false` | Prune Docker system |
| `cleanup_build` | `false` | Clean build directories |
| `cleanup_target` | `false` | Clean target directories |
| `warning_disk_percent` | `80` | Disk usage warning threshold |
| `critical_disk_percent` | `90` | Disk usage critical threshold |
| `large_file_threshold` | `1GB` | Threshold for large file detection |
| `max_logs` | `50` | Maximum log files to keep |

### Data storage:
- **Logs:** `~/.local/share/linux-health/logs/` (JSON files, auto-rotated)
- **History:** `~/.local/share/linux-health/history.json` (last 50 entries)

### Loading logic:
```python
config = DEFAULT_CONFIG.copy()
if ~/.config/linux-health/config.toml exists:
    try: parse TOML, merge into config
    except: silently use defaults
```

---

## 4. Module-by-Module Breakdown

### 4.1 `utils.py` — Shared Helpers

| Function | What it does |
|---|---|
| `human_size(bytes)` | Convert raw bytes to human string (1.5GB, 3.2MB, etc.) |
| `parse_size(str)` | Reverse of human_size, e.g. "1GB" → 1073741824 |
| `get_dir_size(path)` | Calculate directory size via `du -sb` (with Python fallback) |
| `command_exists(cmd)` | Check if a binary exists in PATH via `shutil.which` |
| `run_cmd(args, timeout)` | Run subprocess, return stdout or None on failure |
| `bytes_percent(used, total)` | Calculate percentage safely |

### 4.2 `config.py` — Configuration

- `load_config()` → merges defaults with user's `~/.config/linux-health/config.toml`
- `ensure_dirs()` → creates config, data, and log directories
- Uses Python's `tomllib` (stdlib in 3.11+)
- No external config parsing dependencies

### 4.3 `logger.py` — Structured Logging

- `write_log(entry)` → writes a JSON file to `~/.local/share/linux-health/logs/{timestamp}.json`
- `_cleanup_old_logs(max_logs)` → auto-deletes oldest logs exceeding the limit
- `get_logs()` → returns all logs sorted newest-first
- Each log contains: timestamp, disk before/after, space freed, actions, warnings, errors

### 4.4 `history.py` — Cleanup History

- `get_history()` → loads `~/.local/share/linux-health/history.json`
- `add_entry(entry)` → prepends entry to history, caps at 50 entries
- History entries: date, freed bytes, actions taken

### 4.5 `health.py` — Dashboard Aggregator

This is the orchestrator for the default `lh` command. It calls every monitoring module and assembles a single dict:

```python
def collect_all() -> dict:
    return {
        "system": get_system_info(),       # hostname, OS, kernel, uptime
        "cpu": cpu.get_info(),              # usage %, core count
        "cpu_temp": cpu.get_temperature(),  # °C
        "ram": memory.get_ram_info(),       # total, used, available, percent
        "swap": memory.get_swap_info(),     # total, used, percent
        "battery": battery.get_info(),      # health, cycles, capacity, status
        "disk": disk.get_disk_usage(),      # mount, total, used, free
        "disk_analysis": disk.analyze_disk(), # mounts, common dirs, large dirs/files
        "network": network.get_info(),      # hostname, IP, connected
        "cache": get_cache_sizes(),         # user cache, pacman, flatpak, thumbnails
        "dev": get_dev_sizes(),             # maven, gradle
        "last_cleanup": ...,                # date string or None
        "next_cleanup": ...,                # date string
    }
```

Also provides `get_doctor_recommendations(data)` which checks:
- Disk usage ≥ 80% → warning, ≥ 90% → critical
- CPU temp ≥ 85°C → warning
- Battery health ≤ 60% → warning
- User cache > 5GB → info
- Pacman cache > 2GB → info

### 4.6 `cpu.py` — CPU Monitoring

- `get_info()` → usage percentage (via psutil or `top`), logical/physical core count
- `get_temperature()` → CPU temp from psutil's `sensors_temperatures()` or `/sys/class/thermal/thermal_zone0/temp`
- Gracefully falls back from psutil to /proc and subprocess when psutil is unavailable

### 4.7 `memory.py` — RAM & Swap

- `get_ram_info()` → total, used, available, percent (via psutil or `/proc/meminfo`)
- `get_swap_info()` → total, used, percent (via psutil or `/proc/meminfo`)
- All values returned in both raw bytes and human-readable format

### 4.8 `disk.py` — Disk Analysis

Key functions:

| Function | Purpose |
|---|---|
| `get_disk_usage(path)` | Single mount point info (psutil or `df -B1`) |
| `get_all_mounts()` | All physical mounts (filters out tmpfs, proc, sysfs, etc.) |
| `scan_common_dirs()` | Sizes of `~/Downloads`, `~/Documents`, `~/.cache`, `~/.config`, `~/.m2`, `~/.gradle`, etc. |
| `get_largest_dirs(base, count, min_size)` | Top N dirs > min_size via `du -sb --max-depth=1` |
| `get_largest_files(search_dirs, count, min_size)` | Top N files > min_size via `find` + `ls` |
| `analyze_disk()` | Runs all of the above and returns a combined dict |

The `analyze_disk()` function returns:
```python
{
    "usage": {...},        # Root mount info
    "mounts": [...],       # All physical mounts
    "common_dirs": [...],  # Directory breakdown with sizes
    "largest_dirs": [...], # Top 15 dirs > 100MB
    "largest_files": [...],# Top 15 files > 100MB
}
```

### 4.9 `battery.py` — Battery Monitoring

Reads everything from `/sys/class/power_supply/BAT*/`:

| Sysfs attribute | What it provides |
|---|---|
| `capacity` | Current charge percentage |
| `status` | Charging/Discharging/Full |
| `cycle_count` | Number of charge cycles |
| `charge_full` / `charge_full_design` | Current and design capacity (µAh) |
| `energy_full` / `energy_full_design` | Current and design capacity (µWh) fallback |
| `charge_now` / `energy_now` | Current charge level |
| `voltage_now` | Current voltage (µV) |
| `current_now` | Current draw (µA, negative = discharging) |
| `power_now` | Power draw (µW) |
| `temp` | Battery temperature (decikelvin → °C) |
| `manufacturer` / `model_name` / `serial_number` | Battery identity |
| `technology` | Li-ion, LiPo, etc. |
| `capacity_level` | Normal/Low/Critical/Ful |

**Calculated fields:**
- `health` = charge_full / charge_full_design × 100
- `degradation` = 100 - health
- `capacity_lost` = design - current (in mAh or Wh)
- `time_remaining` = energy_now / power_now (discharging) or (energy_full - energy_now) / power_now (charging)

### 4.10 `netdiag.py` — Network Diagnostics

| Function | Data source |
|---|---|
| `get_interfaces()` | `ip -o addr show`, `ip -o link show`, `/sys/class/net/*/speed` |
| `get_gateway()` | `ip route show default` |
| `get_dns()` | `/etc/resolv.conf`, `resolvectl dns` |
| `ping_test(target)` | `ping -c 3 -W 3` → latency, loss % |
| `dns_resolve(hostname)` | `socket.getaddrinfo()` with timing |
| `get_listening_ports()` | `ss -tlnp` |
| `get_active_connections()` | `ss -tn state established` |
| `get_wifi_info()` | `iw dev <iface> link` → SSID, signal dBm, freq, bitrate |
| `get_public_ip()` | `curl ifconfig.me` |
| `collect_all()` → | Returns all the above in one dict |

### 4.11 `security.py` — Security Audit

| Function | What it checks |
|---|---|
| `get_failed_ssh_attempts()` | Count "Failed password" in `journalctl -u sshd` (30 days) |
| `get_open_ports_local()` | All listening TCP ports via `ss -tlnp` |
| `check_suid_files()` | SUID files not owned by root (`find / -perm -4000 ! -user root`) |
| `check_world_writable()` | World-writable files in `/etc` |
| `check_uid_zero()` | Non-root users with UID 0 |
| `check_recent_timers()` | Systemd timers modified in last 7 days |
| `check_recent_cron()` | Cron files modified in last 7 days |
| `check_arch_audit()` | Known vulnerable packages via `arch-audit` |

### 4.12 `boot.py` — Boot & Kernel Analysis

| Function | What it checks |
|---|---|
| `get_installed_kernels()` | All kernels in `/usr/lib/modules` with sizes |
| `get_current_kernel()` | `uname -r` |
| `get_latest_kernel_pkg()` | `pacman -Qi linux` → version |
| `get_boot_usage()` | `df -B1 /boot` |
| `get_grub_config()` | Parses `/etc/default/grub` |
| `get_systemd_analyze_blame()` | `systemd-analyze blame` (top 15) |
| `get_systemd_analyze_time()` | `systemd-analyze time` |
| `get_systemd_analyze_critical()` | `systemd-analyze critical-chain` |
| `get_dmesg_errors()` | `dmesg -l err -P` (last 20) |
| `get_failed_services()` | `systemctl --failed` (user + system) |
| `get_old_kernels_for_removal()` | All kernels except the running one |

### 4.13 `sensors.py` — Hardware Sensor Readout

| Function | What it reads |
|---|---|
| `get_cpu_temps_per_core()` | `/sys/class/thermal/thermal_zone*/temp` + `sensors -u` |
| `get_fan_speeds()` | `/sys/class/hwmon/hwmon*/fan*_input` + `sensors` |
| `get_gpu_info()` | NVIDIA: `nvidia-smi`; AMD/Intel: `/sys/class/drm/card*/device/hwmon` |
| `get_disk_temps()` | NVMe: `/sys/class/nvme/nvme*/device/temp` + `sudo nvme list`; HDD: `sudo smartctl` |
| `get_battery_temp()` | `/sys/class/power_supply/BAT*/temp` |
| `get_power_consumption()` | `/sys/class/powercap/*/energy_uj` + `powertop` |

### 4.14 `update.py` — System Update

**Pre-flight checks (no sudo needed):**

| Check | Command |
|---|---|
| Partial upgrades | `pacman -Qk --quiet` → count of missing files |
| Orphaned packages | `pacman -Qtdq` |
| Held packages | Parses `IgnorePkg` from `/etc/pacman.conf` |
| Pending updates | `pacman -Sup --print-format %n` → package count |
| AUR updates | `yay -Qua` or `paru -Qua` → count |
| Systemd boot analysis | `systemd-analyze blame` → top 10 slow services |

**Update execution (requires sudo):**
- Runs `sudo pacman -Syu --noconfirm` (timeout: 5 minutes)
- Captures stdout/stderr

**Post-update checks:**
- `pacman -Q --check` → detects libraries needing service restart
- Checks for `/run/reboot-required`

### 4.15 `cleanup.py` — Cleanup Engine

**Cleanup flow:**

```
run_cleanup(dry_run)
  │
  ├── clean_cache()         # Removes only SAFE_CACHE_DIRS from ~/.cache
  ├── clean_thumbnails()    # Removes ~/.cache/thumbnails
  ├── clean_tmp()           # Removes /tmp contents
  ├── clean_journal()       # journalctl --vacuum-time=7d
  ├── clean_pacman()        # paccache -rk2
  ├── clean_flatpak()       # flatpak uninstall --unused
  └── clean_docker()        # docker system prune -f
```

**Safe cache protection:** The `clean_cache()` function uses a whitelist approach:
- **Only removes:** `pip/`, `yay/`, `paru/`, `go-build/`, `npm/`, `pnpm/`, `cargo/`, `rustup/`, `composer/`, `gem/`, `mypy/`, `black/`, `ruff/`, `pytest/`, `httpie/`, `wget/`, `curl/`, `.tmp`/`.log` files
- **Never touches:** `waybar/`, `fontconfig/`, `wal/`, `mesa/`, `nv/`, `amd/`, `sway/`, `hyprland/`, `gnome-shell/`, `plasma/`, `pulse/`, `pipewire/`, `wireplumber/`, `mozilla/`, `chromium/`, `firefox/`, `discord/`, `spotify/`, `code/`, `thumbnails/`, and 20+ more

**Safety guarantees:**
1. `--dry-run` always available → preview before deleting
2. Every deletion is logged to JSON
3. Never deletes: ~/Downloads, ~/Documents, ~/Desktop, ~/Pictures, ~/Videos, ~/Music, git repos, source code, Maven repos, Gradle caches, Docker images, target/build folders
4. Missing programs are handled gracefully (e.g., if `paccache`/`flatpak`/`docker` is not installed, that step is skipped)

### 4.16 `pacman.py`, `flatpak.py`, `docker.py`, `java.py` — Specialized Cleanup

Each module has the same interface:
```python
def clean(dry_run: bool = False) -> dict:
    # Returns {"freed": int, "actions": list[str], "error": str | None}
```

### 4.17 `notifications.py` — Desktop Notifications

- `send_cleanup_notification(freed)` → calls `notify-send` with freed space info
- Silently fails if `notify-send` is not available

### 4.18 `report.py` — Rich Output Formatting

This is the view layer. Every `show_*_report()` function:
1. Receives a dict of data
2. Formats it using **Rich** (Panel, Table, Text, Progress bar)
3. Prints to the console

**Output functions:**

| Function | Used by | Sections |
|---|---|---|
| `show_dashboard()` | `lh` (default) | SYSTEM, CPU, MEMORY, SWAP, BATTERY, STORAGE, TOP DIRECTORIES, CACHE, DEVELOPMENT, WARNINGS, footer |
| `show_disk_analysis()` | `--disk` | DISK USAGE (with bar), Mount Points, Directory Breakdown (% of disk), Largest Directories, Largest Files |
| `show_battery_report()` | `--battery` | CHARGE (bar + %), HEALTH & INFO (health bar, degradation, cycles, technology, manufacturer), ELECTRICAL (capacity, voltage, power), RECOMMENDATIONS |
| `show_update_report()` | `--update` | PRE-FLIGHT CHECKS (pending, partial, orphans, held, AUR), update output, services needing restart |
| `show_net_report()` | `--net` | CONNECTIVITY, per-interface details, WIFI, PING (Cloudflare + Google), DNS RESOLUTION, listening ports, active connections |
| `show_security_report()` | `--security` | Failed SSH, open ports, SUID issues, world-writable /etc, UID 0 users, vulnerability audit, recent cron/timers |
| `show_boot_report()` | `--boot` | KERNEL (running + latest), installed kernels with status, /BOOT USAGE, GRUB config, boot time, slowest services, failed services, dmesg errors |
| `show_sensors_report()` | `--sensors` | CPU TEMPERATURES per core, GPU (temp/usage/power), FAN SPEEDS, DISK TEMPERATURES, battery temp, power consumption |
| `show_doctor_results()` | `--doctor` | Host/OS/Uptime, per-warning with severity icon |
| `show_cleanup_summary()` | `--clean` | Per-cleaner freed space, actions taken, total freed |
| `show_history()` | `--history` | Table of dates, freed space, actions |
| `show_help()` | `--help` | Custom rich help page with all commands, descriptions, config info |
| `show_deep_scan_results()` | `--kernel`, `--malware` | Score bar + per-finding severity panels |
| `show_findings_summary()` | All severity-classified commands | Reusable finding panel renderer |

**Visual elements used:**
- `Panel` — section containers with colored borders
- `Table` — key-value and multi-column layouts
- `Text` — styled text with alignment
- `fmt_usage_bar()` — custom block-character progress bars (█/░)
- Color coding: green (good), yellow (warning), red (critical), cyan (info), blue (section headers)

### 4.18 `collectors/base.py` — Enhanced Finding Class

```python
@dataclass
class Finding:
    module: str         # e.g. "kernel", "malware", "hardware.input"
    title: str          # Short name
    detail: str         # What was found
    severity: str       # "pass" | "info" | "warning" | "critical"
    confidence: int     # 0-100 how sure we are
    impact: str         # "low" | "medium" | "high" | "critical"
    expected: bool      # True = expected behavior (e.g. NVIDIA taint on gaming laptop)
    fixable: bool       # Can the user fix this?
    risk: str           # "safe" | "low" | "moderate" | "high" | "dangerous"
    category: str       # "kernel" | "malware" | "hardware" | "network" | ...
    description: str    # Human-readable explanation of what this is
    evidence: dict      # Supporting data
    suggestion: str     # What to do about it
```

**Smart scoring formula:**
```
penalty = SEVERITY_WEIGHT × IMPACT_MULTIPLIER × (0.2 if expected else 1.0) × (confidence / 100)

Critical = 10 points    × impact (1-3x) × expected (0.2x) × confidence
Warning  = 5 points     × impact (1-3x) × expected (0.2x) × confidence
Info     = 2 points     × impact (1-3x) × expected (0.2x) × confidence

Cap: 30 points per category
```

**Example — NVIDIA taint (expected, low impact):** `5 × 1 × 0.2 × 1.0 = 1.0` penalty (negligible)
**Example — ASLR disabled (unexpected, critical):** `10 × 3 × 1.0 × 1.0 = 30.0` penalty (significant)

**Collectors tier system:**
- `fast` — runs on `lh` default dashboard (<1s)
- `standard` — runs on `--doctor`, `--kernel`, `--sensors`
- `deep` — runs only on explicit `--malware`

```python
class BaseCollector(ABC):
    name: str
    tier: str           # "fast" | "standard" | "deep"
    def collect() -> list[Finding]
```

Every collector implements this interface. The `tier` controls when it runs:
- **fast** — runs on `lh` default dashboard
- **standard** — runs on `--doctor`, `--kernel`, `--sensors`
- **deep** — runs only on explicit `--malware`

### 4.19 `collectors/kernelcheck.py` — Kernel-Level Checker

| Check | Source | Severity |
|---|---|---|
| ASLR status | `/proc/sys/kernel/randomize_va_space` | critical if 0 |
| Ptrace scope | `/proc/sys/kernel/yama/ptrace_scope` | warning if 0 |
| Kptr restrict | `/proc/sys/kernel/kptr_restrict` | info if 0 |
| Dmesg restrict | `/proc/sys/kernel/dmesg_restrict` | info if 0 |
| Kexec disabled | `/proc/sys/kernel/kexec_disabled` | warning if 0 |
| Kernel taint | `/proc/sys/kernel/tainted` (26 bits decoded) | warning/critical |
| CPU vulnerabilities | `/sys/devices/system/cpu/vulnerabilities/*` | warning if "Vulnerable" |
| AppArmor/SELinux | `/sys/module/apparmor/...`, `/sys/fs/selinux/enforce` | info if disabled |
| Boot params | `/proc/cmdline` — dangerous flags | critical |
| dmesg errors | `dmesg -l err -P` | info |
| Out-of-tree modules | `lsmod` — check against known list | info |

### 4.20 `collectors/malware.py` — Malware & Rootkit Scanner

| Check | Method | Severity |
|---|---|---|
| Hidden processes | Compare `/proc` PIDs vs `ps aux` PIDs | critical |
| Rootkit file paths | 30+ known rootkit file locations | critical |
| Unusual SUID | `find / -perm -4000` vs known-safe list | warning |
| World-writable PATH | Check every `$PATH` dir for `o+w` | critical |
| Suspicious cron | Cron jobs executing from `/tmp`, `/dev/shm` | warning |
| Unknown high ports | `ss -tlnp` — ports >1024 not in known services | info |

### 4.21 `collectors/hardware_scanner.py` — Hardware Inventory with Condition %

Scans all detectable system devices and reports each with a condition percentage:

| Category | Devices | Condition basis |
|---|---|---|
| **Input** | Keyboard, Touchpad, Mouse, Lid Switch, Power Button, Camera, Tablet | Touchpad: IRQ spread analysis; others: 100% if detected |
| **Power** | AC Adapter (Charger), Battery | Charger: 100% if online; Battery: from capacity or health |
| **Thermal** | All thermal zones | 100% under 60°C → 10% at 95°C+ |
| **Fans** | Every fan from hwmon/sensors | 100% if RPM > 500, 80% if >0, 50% if stopped |
| **GPU** | NVIDIA (via nvidia-smi), AMD/Intel (via sysfs) | Based on temperature |
| **USB** | All USB devices with speed | Speed tier: USB 3.x=100%, 2.0=85%, 1.x=60% |

Condition severity mapping:
- ≥80% → pass (Excellent/Good)
- ≥50% → info (Fair)
- ≥25% → warning (Poor)
- <25% → critical (Critical)

### 4.22 `engine/runner.py` — Collector Runner

```python
def run_collectors(collectors, tier="fast") -> list[Finding]
```

- Runs each collector's `collect()` method sequentially
- Filters by tier: `fast` only, `standard` = fast+standard, `deep` = all
- Catches exceptions per-collector so one failure never crashes the whole run
- Returns combined list of findings

### 4.23 `engine/scoring.py` — Smart Health Score Engine

The scoring engine uses intelligent weighting with four factors:

| Factor | Values | Effect |
|---|---|---|
| Severity weight | critical=10, warning=5, info=2 | Base penalty |
| Impact multiplier | critical=3x, high=2x, medium=1.5x, low=1x | Scales penalty by real-world impact |
| Expected multiplier | expected=0.2x, unexpected=1x | Expected findings (NVIDIA taint) get 80% discount |
| Confidence multiplier | 0-100% | Low-confidence findings contribute less |

```python
def calculate_score(findings: list[Finding]) -> float:
    penalty = min(SUM(findings), 30)  # cap per category
    return max(0, 100 - penalty)

def compute_overall_score(category_scores: dict) -> float:
    return average of all non-empty category scores
```

Categories scored independently: kernel, malware, hardware, disk, battery, network, boot.
Each category capped at 30 penalty (70 minimum score for one critical finding).

### 4.24 `engine/runner.py` — Parallel Collector Runner

Runs collectors using `ThreadPoolExecutor` for concurrent execution:

```python
def run_collectors(collectors, tier="fast", parallel=True) -> list[Finding]
```

- Filters collectors by tier (fast/standard/deep)
- Parallel execution with up to 4 workers for multiple collectors
- Falls back to sequential for single collector or when parallel=False
- 30-second timeout per collector
- Independent failure isolation — one failed collector never crashes the run

### 4.25 `trash.py` — Rollbackable Cleanup System

The rollback system replaces permanent deletion with reversible snapshots.

**Trash directory:** `~/.local/share/linux-health/trash/`

**Cleanup flow:**
```
lh --clean
  → Files moved to trash/cleanup_YYYYMMDD_HHMMSS/
  → Manifest created with original paths, sizes, timestamps
  → 24-hour retention by default
  → lh --restore list shows available snapshots
  → lh --restore <id> restores files atomically
  → lh --purge-trash removes all snapshots immediately
```

**Key functions:**

| Function | Role |
|---|---|
| `trash_item(src)` | Moves a file/dir to rollback storage |
| `create_manifest(id, items, actions)` | Creates JSON manifest with metadata |
| `get_snapshots()` | Lists all available rollback snapshots |
| `restore_snapshot(id)` | Restores a snapshot to original locations |
| `purge_trash()` | Permanently deletes all snapshots |
| `remove_expired(hours)` | Deletes snapshots older than retention period |

**Manifest format:**
```json
{
    "id": "cleanup_20260719_214511",
    "created": "2026-07-19T21:45:11",
    "expires": "2026-07-20T21:45:11",
    "freed": 4500000000,
    "items": [
        {"original": "/home/user/.cache/pip", "trashed": ".../trash/cleanup_.../cache_pip", "size": 4200000000}
    ]
}
```

**Safety:**
- Uses `shutil.move()` for instant, zero-copy moves (same filesystem)
- Verifies original path is safe to recreate before restoring
- Each snapshot is independent — restore one without affecting others
- Auto-expired via systemd timer (configurable, default 24h, max 7d)

### 4.26 `boot.py` — Proper Version Comparison

Uses `vercmp` (the standard Arch Linux version comparison tool) instead of string comparison:

```python
def vercmp(v1, v2) -> int:     # Returns -1, 0, or 1
def is_newer_kernel_available(current, latest) -> bool:
```

This prevents false positives like:
- `7.1.3-arch1-2` vs `7.1.3.arch1-2` → vercmp says equal (correct)
- `7.2.0` vs `7.1.3` → vercmp says newer (correct)

---

## 5. Systemd Integration

### 5.1 Timer (`linux-health.timer`)

```ini
[Unit]
Description=Linux Health Weekly Maintenance Timer

[Timer]
OnCalendar=weekly
Persistent=true        # Runs missed events on next boot
RandomizedDelaySec=30m # Spreads load across users

[Install]
WantedBy=timers.target
```

### 5.2 Service (`linux-health.service`)

```ini
[Unit]
Description=Linux Health Weekly Maintenance

[Service]
Type=oneshot
ExecStart=%h/.local/bin/linux-health --clean

[Install]
WantedBy=default.target
```

Both files are installed to `~/.config/systemd/user/` (not system-wide), so they run as the user without root.

### 5.3 Touchpad IRQ Affinity Service (optional)

```ini
[Unit]
Description=Set touchpad IRQ affinity for smooth cursor

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo fff > /proc/irq/27/smp_affinity; echo fff > /proc/irq/155/smp_affinity'

[Install]
WantedBy=multi-user.target
```

This service spreads touchpad interrupts across all 12 CPU cores, eliminating the single-CPU bottleneck that causes the touchpad to become sluggish when that CPU is busy. Requires `sudo` and is installed to `/etc/systemd/system/`.

### 5.4 CPU Governor Service (user-level, passwordless)

Same repo also contains a companion service at `~/.config/systemd/user/linux-health-cpugov.service` that sets the CPU governor to `performance` at boot using the existing sudoers NOPASSWD rule for `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`.

---

## 6. Installation & Uninstallation

### 6.1 `install.sh`

1. Installs the Python package via `pip install --user`
2. Falls back to `--break-system-packages` for PEP 668 environments
3. Creates default config at `~/.config/linux-health/config.toml`
4. Installs `linux-health.service` and `linux-health.timer` to `~/.config/systemd/user/`
5. Enables and starts the timer
6. Creates `lh` symlink

### 6.2 `uninstall.sh`

1. Stops and disables the timer
2. Removes systemd unit files
3. Removes `lh` symlink
4. Uninstalls the Python package
5. Removes config directory
6. **Preserves logs** unless user confirms deletion

### 6.3 Package build (`pyproject.toml` + `setup.cfg`)

Standard Python build system using setuptools:
- Entry point: `linux-health = linux_health.cli:app`
- Dependencies: `rich>=13`, `psutil>=5`, `typer>=0.9`
- Python requirement: >= 3.10

---

## 7. Data Flow Examples

### 7.1 Default dashboard (`lh`)

```
cli.py:main() → ensure_dirs()
              → collect_all()
                    → health.get_system_info()
                    → cpu.get_info() + get_temperature()
                    → memory.get_ram_info() + get_swap_info()
                    → battery.get_info()
                    → disk.get_disk_usage()
                    → disk.analyze_disk()
                    → network.get_info()
                    → health.get_cache_sizes()
                    → health.get_dev_sizes()
                    → history.get_history()
                    → collectors.healthcheck.run_all_checks(tier="standard")
                          → KernelCheckCollector.collect()
                                → /proc/sys/kernel/* (ASLR, ptrace, taint, etc.)
                                → /sys/devices/system/cpu/vulnerabilities/*
                                → lsmod, dmesg, apparmor/selinux, /proc/cmdline
                          → MalwareCollector.collect()
                                → SUID find, /proc vs ps PID comparison
                                → rootkit paths, cron audit, PATH check, ss ports
                          → engine.scoring.calculate_score() for each category
              → get_doctor_recommendations(data)
              → show_dashboard(data, warnings)
                    → HEALTH SCORE panel (overall score, severity counts, per-category)
                    → SYSTEM, CPU, MEMORY, SWAP, BATTERY, STORAGE, etc.
```

### 7.2 Cleanup (`lh --clean`)

```
cli.py:main() → run_cleanup(dry_run=False)
              → for each enabled cleaner:
                    clean_cache(False)        # only safe cache dirs
                    clean_thumbnails(False)
                    clean_tmp(False)
                    clean_journal(False)
                    clean_pacman(False)
                    clean_flatpak(False)
              → add_entry() (history)
              → write_log() (JSON log)
              → show_cleanup_summary(summary)
              → if notifications: send_cleanup_notification(freed)
```

### 7.3 Battery report (`lh --battery`)

```
cli.py:main() → generate bat_findings (health%, cycles, degradation thresholds)
              → show_findings_summary(bat_findings)
              → get_battery_info()
                    → _find_battery() → /sys/class/power_supply/BAT0/
                    → reads 15+ sysfs attributes
                    → calculates health, degradation, time remaining
              → show_battery_report(bat_data)
                    → CHARGE panel (bar, %, status, time)
                    → HEALTH & INFO panel (degradation, cycles, technology, ...)
                    → ELECTRICAL panel (capacity, voltage, power)
                    → RECOMMENDATIONS panel
```

### 7.4 Kernel analysis (`lh --kernel`)

```
cli.py:main() → KernelCheckCollector.collect()
              → /proc/sys/kernel/randomize_va_space           → ASLR score
              → /proc/sys/kernel/yama/ptrace_scope            → ptrace restriction
              → /proc/sys/kernel/kptr_restrict                → pointer exposure
              → /proc/sys/kernel/dmesg_restrict               → log restriction
              → /proc/sys/kernel/kexec_disabled               → kexec safety
              → /proc/sys/kernel/tainted                      → taint decoding
              → /sys/devices/system/cpu/vulnerabilities/*     → CPU vulns
              → /sys/module/apparmor/parameters/enabled       → AppArmor status
              → /sys/fs/selinux/enforce                       → SELinux status
              → /proc/cmdline                                 → dangerous params
              → dmesg -l err -P                                → kernel errors
              → lsmod → detect out-of-tree modules
              → engine.scoring.calculate_score(findings)
              → show_deep_scan_results("Kernel Analysis", findings, score)
```

### 7.5 Malware scan (`lh --malware`)

```
cli.py:main() → MalwareCollector.collect()
              → find / -perm -4000 -type f → SUID audit vs known-safe list
              → os.listdir('/proc') vs ps aux → PID hiding detection
              → Check 30+ known rootkit paths → rootkit file detection
              → grep cron files for /tmp, /dev/shm execution → suspicious cron
              → Check each $PATH dir for o+w permission → PATH hijack risk
              → ss -tlnp4 → flag unknown high port listeners
              → engine.scoring.calculate_score(findings)
              → show_deep_scan_results("Malware Scan", findings, score)
```

### 7.6 Hardware sensors (`lh --sensors`)

```
cli.py:main() → HardwareScannerCollector.collect()
              → /sys/class/input/event* → all input devices + IRQ for touchpad
              → /sys/class/power_supply/* → AC adapter + battery
              → /sys/class/thermal/thermal_zone* → all temperature sensors
              → /sys/class/hwmon/hwmon*/fan*_input → all fan speeds
              → nvidia-smi or /sys/class/drm/ → GPU info
              → /sys/bus/usb/devices/ → all USB devices
              → engine.scoring.calculate_score(findings)
              → get_sensors_info() (existing detailed sensor data)
              → show_sensors_report(info, hw_findings, score)
                    → Hardware Condition score bar
                    → show_findings_summary(hw_findings)
                    → CPU TEMPERATURES, GPU, FAN SPEEDS panels
```

---

## 8. Key Design Decisions

### 8.1 Single callback pattern
All commands are boolean flags on a single `@app.callback`. This gives `lh --disk --clean` potential (only the first matched flag runs). Subcommands were avoided because flags are faster to type and match the user's stated preference for shortcuts.

### 8.2 No background daemon
The tool runs as a one-shot command. Background automation is handled entirely by systemd timer. This means zero resource consumption between runs.

### 8.3 Safe-by-default cleanup
The cache cleaner uses a whitelist rather than a blacklist. Only known disposable caches are removed. Application runtime state (Waybar, PulseAudio, GPU shader caches, browser profiles, etc.) is never touched.

### 8.4 psutil optional, not required
While psutil is the primary data source for CPU/memory/disk, every module has a fallback using `/proc`, `/sys`, or Linux command-line tools. The tool works even if psutil fails to import.

### 8.5 Structured data in, rich formatting out
Every module returns plain dicts/lists. Formatting is entirely handled by `report.py`. This separation makes it straightforward to add JSON export (`--json`) or alternative output formats.

---

## 9. Complete Command Reference

| Command | What it does | Data sources | Severity findings |
|---|---|---|---|
| `lh` | Full system dashboard + health score | All modules + kernel/malware collectors | Yes (health score bar) |
| `lh --scan` | Dashboard, no cleanup | Same as `lh` | Yes |
| `lh --clean` | Safe cleanup (cache, tmp, journal, pacman, flatpak) | `cleanup.py` | — |
| `lh --clean --dry-run` | Preview only, no deletes | Same, dry_run=True | — |
| `lh --disk` | Disk analysis + severity findings | `disk.py`: df, du, find | Yes (usage%, mounts, large files) |
| `lh --battery` | Battery report + severity findings | `/sys/class/power_supply/BAT*/` | Yes (health, cycles, degradation) |
| `lh --update` | System update + pre-flight checks | `pacman`, `yay`/`paru` | — |
| `lh --net` | Network diagnostics + severity findings | `ip`, `ping`, `ss`, `iw`, `curl`, DNS | Yes (connectivity, latency, WiFi) |
| `lh --security` | Security audit | `journalctl`, `find`, `ss`, `arch-audit` | — |
| `lh --boot` | Boot/kernel analysis + severity findings | `uname`, `df`, `systemd-analyze`, `dmesg`, `systemctl` | Yes (failed services, errors, old kernels) |
| `lh --sensors` | Hardware inventory with condition % | `collectors/hardware_scanner.py` + `sensors.py` | Yes (condition % per device) |
| `lh --kernel` | Deep kernel analysis + severity findings | `collectors/kernelcheck.py` | Yes (taint, ASLR, vulns, LSM) |
| `lh --malware` | Malware/rootkit scan + severity findings | `collectors/malware.py` | Yes (hidden procs, rootkits, SUID) |
| `lh --doctor` | Diagnostics + recommendations | All monitoring modules + threshold checks | — |
| `lh --history` | Cleanup history | `~/.local/share/linux-health/history.json` | — |
| `lh --version` | Show version | `__init__.py` | — |
| `lh --help` | Custom rich help page | `report.py:show_help()` | — |

---

## 10. Filesystem Footprint

| Category | Size | Location |
|---|---|---|
| Source code | ~1.3 MB | `~/linux-health/linux_health/` |
| Installed package | ~50 KB | `~/.local/lib/python*/site-packages/linux_health/` |
| Dependencies (rich + psutil + typer) | ~4.7 MB | `~/.local/lib/python*/site-packages/` |
| Configuration | < 100 bytes | `~/.config/linux-health/config.toml` |
| Logs (max) | 5 MB | `~/.local/share/linux-health/logs/` |
| History | < 10 KB | `~/.local/share/linux-health/history.json` |
| **Total** | **< 50 MB** | |

---

## 11. Security Model

- **No root required** for normal operation (dashboard, battery, network, sensors, etc.)
- **Root required** for: `--update` (pacman -Syu), journal cleanup, IRQ affinity changes
- **Passwordless sudo** works for CPU governor changes via existing `/etc/sudoers` NOPASSWD rule
- **Every deletion is logged** with timestamp, before/after sizes, and action list
- **Dry-run mode** shows exact deletions before committing
- **Missing commands handled gracefully** (e.g., no error if `nvidia-smi` or `docker` is absent)
- **Safe cache whitelist** prevents accidental deletion of application runtime state

---

## 12. Extending the Tool

To add a new `lh --foo` command:

### Option A — Simple module (for data display commands)

1. Create `linux_health/foo.py` with a `collect_all() -> dict` function
2. Add `show_foo_report()` to `report.py` with Rich formatting
3. Add a `foo` option to the callback in `cli.py`
4. Add the routing logic in the callback body
5. Update `show_help()` in `report.py` with the new command description

### Option B — Collector pattern (for severity-classified findings)

1. Create `linux_health/collectors/foo.py` with a class extending `BaseCollector`
2. Implement `collect() -> list[Finding]` with severity levels
3. Wire into `engine/runner.py` via `run_collectors()`
4. Display results via `show_findings_summary()` or `show_deep_scan_results()`
5. Add flag routing in `cli.py`

The architecture is designed for this — every component is independent, communicates via plain dicts or `Finding` objects, and is wired through `cli.py`.

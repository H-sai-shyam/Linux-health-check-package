# Linux Health — Upgrade Plan

## Goal
Turn `lh` into a comprehensive system health checker covering kernel, hardware, software, malware, security, and cache — all from a single terminal command.

---

## Architecture

Every check is a **collector** with a uniform interface:

```python
# collectors/base.py
@dataclass
class Finding:
    module: str          # e.g. "kernel", "malware", "disk"
    title: str           # Short name
    detail: str          # What was found
    severity: str        # "info" | "warning" | "critical" | "pass"
    evidence: dict       # Supporting data
    suggestion: str      # What to do about it

class BaseCollector:
    name: str
    tier: str            # "fast" | "standard" | "deep"
    def collect() -> list[Finding]
```

Collectors are grouped into **categories**, each with a **0–100 health score**:

```
SYSTEM      = average(CPU, memory, swap, disk)
HARDWARE    = average(battery, temps, fans, GPU, SMART)
KERNEL      = average(taint, vulnerabilities, modules, security_settings)
SOFTWARE    = average(integrity, updates, orphans)
MALWARE     = average(rootkits, hidden_procs, suspicious_files, integrity)
NETWORK     = average(connectivity, ports, firewall)
OVERALL     = average(all categories)
```

---

## Phase 1 — Collector Framework + Scoring Engine

**Files to create/modify:**

| File | What |
|---|---|
| `linux_health/collectors/base.py` | `Finding` dataclass, `BaseCollector` ABC |
| `linux_health/engine/__init__.py` | Package init |
| `linux_health/engine/scoring.py` | Health score calculator (0–100 per category) |
| `linux_health/engine/runner.py` | Runs all collectors with timeout, collects Findings |

**Example Finding:**

```python
Finding(
    module="kernel",
    title="Kernel is tainted",
    detail="Bit 12 set: unsigned module loaded",
    severity="warning",
    evidence={"taint_bits": "12", "module": "nvidia"},
    suggestion="Use signed modules or sign the nvidia driver"
)
```

**Score calculation:**
```
critical finding = -25 points per finding (cap -100 per category)
warning  finding = -10 points per finding (cap -50 per category)
info     finding = -2  points per finding (cap -10 per category)
pass     finding = +0 points (no impact)

category_score = max(0, 100 - deductions)
overall_score = average of all non-empty category scores
```

---

## Phase 2 — Kernel-level Checker

**File:** `linux_health/collectors/kernelcheck.py`

| Check | Source | Severity if issue found |
|---|---|---|
| **Kernel taint** | `/proc/sys/kernel/tainted` — decode each bit | warning |
| **CPU vulnerabilities** | `/sys/devices/system/cpu/vulnerabilities/*` | warning if "Vulnerable" |
| **Loaded modules** | `lsmod` — flag unsigned / uncommon modules | info |
| **ASLR** | `/proc/sys/kernel/randomize_va_space` | critical if 0 |
| **Ptrace scope** | `/proc/sys/kernel/yama/ptrace_scope` | warning if 0 |
| **Kexec** | `/proc/sys/kernel/kexec_disabled` | warning if 0 |
| **Kptr_restrict** | `/proc/sys/kernel/kptr_restrict` | info if 0 |
| **Dmesg restrict** | `/proc/sys/kernel/dmesg_restrict` | info if 0 |
| **AppArmor** | `/sys/module/apparmor/parameters/enabled` | warning if disabled |
| **SELinux** | `/sys/fs/selinux/enforce` | warning if permissive/disabled |
| **Kernel errors** | `dmesg -l err` — count and sample | info |
| **Boot cmdline** | `/proc/cmdline` — flag dangerous options | warning for `mitigations=off`, `pti=off`, etc. |
| **Kernel live patch** | Check for `livepatch` in `lsmod` or `/sys/kernel/livepatch` | info if no livepatch |

**Example output:**
```
KERNEL HEALTH: ████████░░ 78/100
  ✓ ASLR enabled (full)
  ✓ Kptr restriction enabled
  ✓ Dmesg restriction enabled
  ⚠ Kernel is tainted (proprietary module: nvidia)
  ⚠ CPU: Vulnerable to Retbleed
  ⚠ AppArmor not detected
```

---

## Phase 3 — Malware Scanner

**File:** `linux_health/collectors/malware.py`

| Check | Method | Severity |
|---|---|---|
| **SUID/SGID audit** | `find / -perm -4000 -o -perm -2000` — flag non-standard binaries | warning |
| **World-writable PATH** | Check every dir in `$PATH` for `o+w` | critical |
| **Hidden processes** | Compare `os.listdir('/proc')` PIDs vs `ps aux` PIDs — PID hiding is classic rootkit | critical |
| **Suspicious cron** | Find cron jobs running from `/tmp`, `/dev/shm`, `/var/tmp` | warning |
| **Suspicious timers** | systemd timers with `ExecStart` in `/tmp` or `/dev/shm` | warning |
| **Common rootkit files** | Check for known rootkit paths (stored in json list) | critical if found |
| **High port listeners** | `ss -tlnp` — flag processes on >1024 that aren't known services | info |
| **SSH authorized_keys** | Count keys, check last modified time | info if >5 keys |
| **Suspicious /tmp** | Files in `/tmp` with executable bit or suspicious names | warning |
| **Listening from world-writable** | Flag any process listening from a world-writable binary path | critical |

---

## Phase 4 — File Integrity Checker

**File:** `linux_health/collectors/integrity.py`

- `--rebaseline` flag to generate SHA-256 hashes of critical paths
- Stores baseline in `~/.local/share/linux-health/baseline.json`
- Default paths: `/usr/bin`, `/usr/sbin`, `/etc`, `/usr/lib`
- Each run diffs current hashes vs baseline
- Flags modified, new, and deleted files
- User can add custom paths in config: `integrity_paths = ["/usr/bin", "/opt/myapp"]`

**Config additions:**
```toml
[integrity]
enable = false  # off by default (first run must --rebaseline)
paths = ["/usr/bin", "/usr/sbin", "/etc"]
ignore_patterns = ["*.lock", "*.pid", "cache/*"]
```

---

## Phase 5 — Enhanced Dashboard + JSON Export

**CLI additions:**

| Flag | What it does |
|---|---|
| `--json` | Export all findings + scores as JSON to stdout |
| `--summary` | One-line health score (for polybar/waybar/scripts) |
| `--rebaseline` | Regenerate file integrity hashes |
| `--kernel` | Run kernel checks only |
| `--malware` | Run malware checks only |
| `--integrity` | Run integrity checks only |

**Dashboard changes:**
- Health score bar at the top
- Findings grouped by severity (colored panels)
- Per-category score display
- `lh --json | jq .` for scripting

---

## Config additions

```toml
[general]
auto_cleanup = true
cleanup_interval_days = 7
notifications = true

[thresholds]
warning_disk_percent = 80
critical_disk_percent = 90
large_file_threshold = "1GB"

[cleanup]
cleanup_cache = true
cleanup_thumbnails = true
cleanup_tmp = true
cleanup_journal = true
cleanup_pacman_cache = true
cleanup_flatpak = true

[kernel_checks]
enable = true
check_vulnerabilities = true
check_taint = true
check_modules = true
check_boot_params = true

[malware_checks]
enable = true
check_suid = true
check_hidden_procs = true
check_rootkit_files = true
check_suspicious_cron = true

[integrity]
enable = false
paths = ["/usr/bin", "/usr/sbin", "/etc"]
```

---

## File structure after upgrade

```
linux_health/
├── __init__.py
├── __main__.py
├── cli.py                  # Flag routing (updated)
├── config.py               # Config loader (updated)
├── utils.py                # Helpers
├── logger.py / history.py  # Existing
├── notifications.py        # Existing
├── collectors/             # NEW — all health checks
│   ├── __init__.py
│   ├── base.py             # Finding, BaseCollector
│   ├── system.py           # CPU, memory, swap (from health.py, cpu.py, memory.py)
│   ├── disk.py             # Disk usage, mounts, files (from disk.py)
│   ├── battery.py          # Battery (from battery.py)
│   ├── network.py          # Network (from netdiag.py)
│   ├── sensors.py          # GPU, temps, fans (from sensors.py)
│   ├── boot.py             # Boot/kernel (from boot.py)
│   ├── security.py         # SSH, ports, SUID (from security.py)
│   ├── kernelcheck.py      # NEW — taint, vulns, modules, ASLR, LSM
│   ├── malware.py          # NEW — rootkits, hidden procs, suspicious files
│   └── integrity.py        # NEW — SHA-256 baseline + diff
├── engine/                 # NEW — scoring + runner
│   ├── __init__.py
│   ├── runner.py           # Runs all collectors
│   └── scoring.py          # Health score calculator
├── cleanup/                # Moved from root
│   ├── __init__.py
│   ├── cache.py            # From cleanup.py
│   ├── pacman.py           # Existing
│   ├── flatpak.py          # Existing
│   └── docker.py           # Existing
├── report/                 # NEW — all output formatting
│   ├── __init__.py
│   ├── dashboard.py        # Main TUI (from report.py)
│   └── json_export.py      # JSON serializer
└── temperature.py / network.py / java.py / update.py
```

---

## What stays the same

- All existing CLI flags continue working (`lh`, `--disk`, `--battery`, etc.)
- Config file path (`~/.config/linux-health/config.toml`)
- Data storage path (`~/.local/share/linux-health/`)
- Install.sh / uninstall.sh
- systemd timer integration
- No new Python dependencies (stdlib only + rich/psutil/typer)

---

## Phase order

| Phase | What | Est. time |
|---|---|---|
| **1** | Collector framework (Finding, BaseCollector, runner, scoring) | 2–3 days |
| **2** | Kernel-level checker | 1–2 days |
| **3** | Malware scanner | 2–3 days |
| **4** | File integrity checker | 1 day |
| **5** | Enhanced dashboard + JSON export + new CLI flags | 1–2 days |
| **6** | Testing, edge cases, docs | 1 day |

Each phase is independent and can be built/tested in isolation.

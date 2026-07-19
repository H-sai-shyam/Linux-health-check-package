# Linux Health (lh)

A comprehensive native Linux system health monitoring and maintenance utility.
Checks kernel health, hardware, software integrity, malware/rootkit signs, security,
network, battery, disk, and more — all from a single terminal command.

## Quick Start

```bash
lh                    # Complete dashboard with health score
lh --kernel           # Deep kernel-level analysis
lh --malware          # Malware & rootkit scan
lh --disk             # Disk usage analysis
lh --battery          # Battery report
lh --doctor           # Diagnose issues
lh --clean            # Run safe cleanup
```

## All Commands

| Command | What it does |
|---|---|
| `lh` | Full dashboard: system, CPU, memory, swap, battery, storage, cache, dev dirs, health score, kernel & malware findings |
| `lh --scan` | Scan only, no cleanup |
| `lh --clean` | Run safe cleanup (cache, thumbnails, tmp, journal, pacman, flatpak) |
| `lh --clean --dry-run` | Preview cleanup without deleting |
| `lh --disk` | Disk analysis: largest dirs, largest files, breakdown, mount points |
| `lh --battery` | Battery report: health %, degradation, time remaining, cycles, voltage |
| `lh --update` | System update with pre-flight checks (orphans, held pkgs, AUR) + pacman -Syu |
| `lh --net` | Network diagnostics: interfaces, gateway, DNS, ping, ports, WiFi |
| `lh --security` | Security audit: SSH attempts, open ports, SUID, world-writable files |
| `lh --boot` | Boot & kernel analysis: kernels, /boot, grub, systemd-analyze, dmesg |
| `lh --sensors` | Hardware sensors: CPU temps, GPU, fans, disk temps, power |
| `lh --kernel` | Deep kernel check: ASLR, taint flags, CPU vulnerabilities, LSM, boot params, dmesg errors, kernel security settings |
| `lh --malware` | Malware & rootkit scan: hidden processes, SUID audit, rootkit paths, suspicious cron/timer, world-writable PATH, unknown port listeners |
| `lh --doctor` | Run diagnostics and get recommendations |
| `lh --history` | Show cleanup history |
| `lh --version` | Show version |
| `lh --help` | Show this help |

## Health Score

Every `lh` run shows a health score (0–100) at the top of the dashboard:

```
HEALTH SCORE: ████████░░ 78/100
  Critical: 0   Warnings: 2   Info: 3
  Per category: kernel: 75  malware: 90
```

Scoring:
- Critical finding: -25 points (cap -100 per category)
- Warning: -10 points (cap -50)
- Info: -2 points (cap -10)
- Pass: no impact

## Kernel Checks (`--kernel`)

| Check | Source | What it detects |
|---|---|---|
| ASLR | `/proc/sys/kernel/randomize_va_space` | Disabled or partial randomization |
| Ptrace scope | `/proc/sys/kernel/yama/ptrace_scope` | Unrestricted ptrace |
| Kptr restrict | `/proc/sys/kernel/kptr_restrict` | Kernel pointers exposed |
| Dmesg restrict | `/proc/sys/kernel/dmesg_restrict` | Unrestricted kernel log access |
| Kexec disabled | `/proc/sys/kernel/kexec_disabled` | Kexec allowed (root can replace kernel) |
| Kernel taint | `/proc/sys/kernel/tainted` | Proprietary/unsigned modules, oops, etc. |
| CPU vulnerabilities | `/sys/devices/system/cpu/vulnerabilities/*` | Spectre, Meltdown, Retbleed, etc. |
| LSM status | `/sys/module/apparmor/parameters/enabled`, `/sys/fs/selinux/enforce` | AppArmor/SELinux disabled |
| Boot params | `/proc/cmdline` | Dangerous params (mitigations=off, pti=off) |
| Kernel errors | `dmesg -l err` | Kernel error count |
| Out-of-tree modules | `lsmod` | Proprietary/out-of-tree kernel modules |

## Malware Checks (`--malware`)

| Check | Method |
|---|---|
| Hidden processes | Compare `/proc` PIDs vs `ps aux` PIDs |
| Rootkit files | Check for known rootkit paths |
| Unusual SUID binaries | Find SUID files outside known-safe list |
| World-writable PATH | Check every $PATH directory for `o+w` |
| Suspicious cron | Cron jobs executing from `/tmp`, `/dev/shm` |
| Unknown port listeners | Services on high ports not matching known services |

## Installation

```bash
chmod +x install.sh
./install.sh
```

### Requirements
- Python 3.10+
- Systemd (for automatic scheduling)
- Packages: `python-rich`, `python-psutil`, `python-typer`

## Automatic Maintenance

A systemd timer runs `lh --clean` weekly. If the system is off on the
scheduled day, it runs on next boot.

## Configuration

`~/.config/linux-health/config.toml`

```toml
auto_cleanup = true
cleanup_interval_days = 7
notifications = true
cleanup_cache = true
cleanup_pacman = true
cleanup_flatpak = true
cleanup_tmp = true
cleanup_journal = true
warning_disk_percent = 80
critical_disk_percent = 90
large_file_threshold = "1GB"
max_logs = 50
```

## Project Size

- Source: <500 KB
- Dependencies: <15 MB
- Logs: max 5 MB
- Total: <50 MB

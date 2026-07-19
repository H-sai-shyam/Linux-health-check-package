# Linux Health — Command Internals Explained

---

## `lh` — Default Dashboard

**What runs:**
```
cli.py:main()
  → health.collect_all()
      → get_system_info()       # /proc/uptime, platform.node(), platform.release()
      → cpu.get_info()          # psutil.cpu_percent() or top -bn1
      → cpu.get_temperature()   # psutil.sensors_temperatures() or /sys/class/thermal/thermal_zone0/temp
      → memory.get_ram_info()   # psutil.virtual_memory() or /proc/meminfo
      → memory.get_swap_info()  # psutil.swap_memory() or /proc/meminfo
      → disk.get_disk_usage()   # psutil.disk_usage("/") or df -B1 /
      → disk.analyze_disk()     # df for mounts, du for dirs, find for files
      → battery.get_info()      # /sys/class/power_supply/BAT0/* (15+ sysfs files)
      → network.get_info()      # hostname -I, ip -4 addr show
      → get_cache_sizes()       # du -sb on ~/.cache, /var/cache/pacman, /var/lib/flatpak
      → get_dev_sizes()         # du -sb on ~/.m2, ~/.gradle
      → collectors.healthcheck.run_all_checks(tier="standard")
          → KernelCheckCollector()  # /proc/sys/kernel/*, /sys/devices/system/cpu/vulnerabilities/*, lsmod, dmesg
          → MalwareCollector()      # SUID find, /proc vs ps, rootkit paths, cron audit, PATH check, ss
          → all findings scored via engine/scoring.py
  → get_doctor_recommendations(data)  # threshold checks on disk%, temp, battery, cache
  → show_dashboard(data, warnings)
      → HEALTH SCORE panel (overall score, severity counts, per-category scores)
      → SYSTEM panel (hostname, OS, kernel, uptime)
      → CPU panel (usage %, temperature)
      → MEMORY panel (RAM used/total, %)
      → SWAP panel (usage %)
      → BATTERY panel (charge %, health, cycles, status, time remaining)
      → STORAGE panel (mount, total, used, free, usage bar)
      → TOP DIRECTORIES panel (largest 6 dirs in ~)
      → CACHE panel (user, pacman, flatpak sizes)
      → DEVELOPMENT panel (maven, gradle)
      → WARNINGS panel (doctor findings)
      → Footer (last cleanup, next cleanup)
```

**Output sections explained:**
```
HEALTH SCORE: ████████░░ 78/100    ← computed from kernel + malware findings
SYSTEM                             ← from /proc, platform module
CPU                                ← psutil or top + sysfs thermal zone
MEMORY                             ← psutil or /proc/meminfo
SWAP                               ← psutil or /proc/meminfo
BATTERY                            ← /sys/class/power_supply/BAT0/*
STORAGE                            ← df -B1 + du -sb
TOP DIRECTORIES                    ← du -sb --max-depth=1 ~/
CACHE                              ← du -sb on cache dirs
DEVELOPMENT                        ← du -sb on .m2, .gradle
WARNINGS                           ← threshold comparisons
```

---

## `lh --kernel` — Kernel-Level Analysis

**What runs:**
```
cli.py:main()
  → KernelCheckCollector.collect()
      → /proc/sys/kernel/randomize_va_space    ASLR enabled? (0=off, 1=partial, 2=full)
      → /proc/sys/kernel/yama/ptrace_scope      Ptrace restriction? (0=any process can ptrace)
      → /proc/sys/kernel/kptr_restrict           Kernel pointers hidden? (0=visible to all)
      → /proc/sys/kernel/dmesg_restrict           dmesg restricted? (0=any user can read kernel logs)
      → /proc/sys/kernel/kexec_disabled           Kexec allowed? (0=root can replace kernel at runtime)
      → /proc/sys/kernel/tainted                  Kernel taint flags (26 bits decoded)
      → /sys/devices/system/cpu/vulnerabilities/* CPU vulns (Spectre, Meltdown, Retbleed, etc.)
      → /sys/module/apparmor/parameters/enabled   AppArmor active?
      → /sys/fs/selinux/enforce                   SELinux enforcing?
      → /proc/cmdline                             Boot params checked for dangerous flags
      → dmesg -l err -P                           Kernel error count
      → lsmod                                     Loaded modules, detect out-of-tree ones
  → engine/scoring.py                             Findings → score
  → show_deep_scan_results("Kernel Analysis", findings, score)
```

**What each check means:**
| Finding | What it tells you |
|---|---|
| ASLR disabled | No address randomization — exploits can predict memory locations |
| Ptrace unrestricted | Any process can debug any other process — privilege escalation risk |
| Kernel pointers exposed | Anyone can see kernel memory addresses — helps attackers |
| dmesg unrestricted | All users can read kernel logs — information leak |
| Kexec allowed | Root can replace the running kernel without reboot |
| Kernel tainted | Proprietary/unsigned modules loaded — can hide malicious code |
| CPU vulnerable | CPU microcode missing — known hardware side-channel attacks possible |
| AppArmor/SELinux off | No mandatory access control — if a process is compromised, it has full access |
| Dangerous boot params | mitigations=off or pti=off explicitly disables CPU vulnerability protections |
| dmesg errors | Kernel errors detected — could indicate hardware issues or driver problems |

---

## `lh --malware` — Malware & Rootkit Scan

**What runs:**
```
cli.py:main()
  → MalwareCollector.collect()
      → _check_suid()             find / -perm -4000 -type f → diff vs known-safe SUID list
      → _check_hidden_processes() os.listdir('/proc') PIDs vs ps aux PIDs → mismatch = PID hiding
      → _check_rootkit_files()    Check existence of 30+ known rootkit paths
      → _check_suspicious_cron()  find cron files that execute scripts from /tmp, /dev/shm
      → _check_world_writable_path()  Check every $PATH directory for o+w permission
      → _check_suspicious_ports() ss -tlnp4 → flag ports >1024 not in known services list
  → engine/scoring.py             Findings → score
  → show_deep_scan_results("Malware Scan", findings, score)
```

**What each check detects:**
| Check | Rootkit technique it catches |
|---|---|
| Hidden processes | LKM rootkits that hide PIDs from ps but not /proc |
| Rootkit file paths | Known malware that drops files at predictable locations |
| Unusual SUID | Backdoors that leave a SUID shell binary |
| World-writable PATH | Anyone can place a malicious executable that gets found first in $PATH |
| Suspicious cron | Persistence via cron jobs that run from /tmp |
| Unknown ports | Backdoor listening for remote connections |

---

## `lh --disk` — Disk Analysis

**What runs:**
```
cli.py:main()
  → health.collect_all() → disk.analyze_disk()
  → show_disk_analysis(disk_analysis)
```

**Data collected:**
| Section | Method |
|---|---|
| DISK USAGE | `df -B1 /` or `psutil.disk_usage("/")` |
| Mount Points | `df -B1 -x tmpfs -x devtmpfs ...` (filters out virtual filesystems) |
| Directory Breakdown | `du -sb` on Downloads, Documents, .cache, .config, .local, .m2, .gradle, etc. |
| Largest Directories | `du -sb --max-depth=1 ~/` → filter >100MB → top 15 |
| Largest Files | `find ~/ -type f -size +100M` → top 15 by size |

---

## `lh --battery` — Battery Report

**What runs:**
```
cli.py:main()
  → battery.get_info()
      → Reads /sys/class/power_supply/BAT0/* (15+ sysfs files)
      → Calculates health, degradation, time remaining
  → show_battery_report(bat)
```

**Sysfs files read:**
| File | Unit | What it provides |
|---|---|---|
| `capacity` | % | Current charge level |
| `status` | string | Charging / Discharging / Full |
| `cycle_count` | number | Battery age |
| `charge_full` / `charge_full_design` | µAh | Current vs design capacity |
| `energy_full` / `energy_full_design` | µWh | Fallback if charge values unavailable |
| `voltage_now` | µV | Current voltage |
| `current_now` | µA | Current draw (negative = discharging) |
| `power_now` | µW | Power consumption |
| `temp` | decikelvin | Battery temperature |
| `manufacturer`, `model_name`, etc. | string | Battery identity |

**Calculated:**
- `health` = charge_full ÷ charge_full_design × 100
- `degradation` = 100 − health
- `time_remaining` (discharging) = energy_now ÷ power_now
- `time_remaining` (charging) = (energy_full − energy_now) ÷ power_now

---

## `lh --net` — Network Diagnostics

**Data sources:**
| Info | Command/file |
|---|---|
| Interfaces + IPs | `ip -o addr show` |
| Interface state/speed | `ip -o link show`, `/sys/class/net/*/speed` |
| Gateway | `ip route show default` |
| DNS | `/etc/resolv.conf`, `resolvectl dns` |
| Ping | `ping -c 3 -W 3 <target>` |
| DNS resolution | `socket.getaddrinfo()` |
| Listening ports | `ss -tlnp` |
| Active connections | `ss -tn state established` |
| WiFi | `iw dev <iface> link` |
| Public IP | `curl ifconfig.me` |

---

## `lh --update` — System Update

**Pre-flight checks:**
| Check | Source |
|---|---|
| Partial upgrades | `pacman -Qk --quiet` → count of missing files |
| Orphans | `pacman -Qtdq` |
| Held packages | Parsed from `/etc/pacman.conf` |
| Pending updates | `pacman -Sup --print-format %n` |
| AUR updates | `yay -Qua` or `paru -Qua` |

**Execution:** `sudo pacman -Syu --noconfirm` (5 min timeout)

**Post-update:** `pacman -Q --check` → detect services needing restart

---

## `lh --security` — Security Audit

| Check | Source |
|---|---|
| Failed SSH logins | `journalctl -u sshd` → "Failed password" count in 30 days |
| Open ports | `ss -tlnp` |
| SUID issues | `find / -perm -4000 ! -user root` |
| World-writable /etc | `find /etc -perm -o=w` |
| UID 0 users | `pwd.getpwall()` → non-root users with uid 0 |
| Recent timers/cron | `find ... -mtime -7` |
| Vulnerable packages | `arch-audit` (if installed) |

---

## `lh --boot` — Boot & Kernel Analysis

| Check | Source |
|---|---|
| Running kernel | `uname -r` |
| Installed kernels | `du -sb /usr/lib/modules/*` |
| Latest kernel pkg | `pacman -Qi linux` |
| /boot usage | `df -B1 /boot` |
| GRUB config | Parsed from `/etc/default/grub` |
| Boot time | `systemd-analyze time` |
| Slow services | `systemd-analyze blame` (top 15) |
| Failed services | `systemctl --failed` (user + system) |
| dmesg errors | `dmesg -l err -P` (last 20) |

---

## `lh --sensors` — Hardware Sensor Readout

| Check | Source |
|---|---|
| CPU temps | `/sys/class/thermal/thermal_zone*/temp` + `sensors` |
| GPU | `nvidia-smi` (NVIDIA) or sysfs (AMD/Intel) |
| Fans | `/sys/class/hwmon/hwmon*/fan*_input` + `sensors` |
| Disk temps | `/sys/class/nvme/*/device/temp`, `smartctl` |
| Battery temp | `/sys/class/power_supply/BAT*/temp` |
| Power | `/sys/class/powercap/*/energy_uj` |

---

## `lh --clean` — Safe Cleanup

| Cleaner | What it does |
|---|---|
| `clean_cache()` | Removes only safe cache dirs from ~/.cache: pip, yay, npm, cargo, etc. |
| `clean_thumbnails()` | Removes ~/.cache/thumbnails |
| `clean_tmp()` | Removes /tmp contents |
| `clean_journal()` | `journalctl --vacuum-time=7d` |
| `clean_pacman()` | `paccache -rk2` |
| `clean_flatpak()` | `flatpak uninstall --unused` |
| `clean_docker()` | `docker system prune -f` |

Protected caches never touched: waybar, fontconfig, mesa, pulse, pipewire, browser profiles, etc.

---

## `lh --doctor` — Diagnostics

Runs threshold checks on the main dashboard data:
- Disk usage ≥ 80% → warning, ≥ 90% → critical
- CPU temp ≥ 85°C → warning
- Battery health ≤ 60% → warning
- User cache > 5GB → info
- Pacman cache > 2GB → info

---

## `lh --history` — Cleanup History

Reads `~/.local/share/linux-health/history.json` (last 50 entries).
Each entry: date, bytes freed, actions taken.

---

## `lh --version`

Prints version from `linux_health/__init__.py: __version__ = "1.0.0"`.

---

## `lh --help`

Custom rich-formatted help page showing all commands, configuration info, and usage notes. Built with Rich Panel + Table components.

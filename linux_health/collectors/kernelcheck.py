from pathlib import Path

from linux_health.collectors.base import BaseCollector, Finding
from linux_health.utils import run_cmd


def _read_sys(path: str) -> str | None:
    try:
        val = Path(path).read_text().strip()
        return val if val else None
    except (OSError, FileNotFoundError):
        return None


def _decode_taint(bits: int) -> list[str]:
    reasons = []
    taint_map = {
        0: ("proprietary module", "A module with a non-GPL license was loaded"),
        1: ("forced module", "A module was force-loaded"),
        2: ("unsupported SMP", "Unsupported SMP configuration"),
        3: ("module out of tree", "A module was loaded from outside the kernel tree"),
        4: ("module retpoline", "A module was built without retpoline"),
        5: ("inline assembly", "Inline assembly in module"),
        6: ("module version magic mismatch", "Module version magic mismatch"),
        7: ("different compiler", "Module compiled with different compiler"),
        9: ("deprecated init", "Module uses deprecated initialization"),
        12: ("unsigned module", "An unsigned module was loaded"),
        13: ("signature verification", "Module signature verification event"),
        14: ("oops occurred", "A kernel oops has occurred"),
        15: ("oops on CPU", "Kernel oops on a specific CPU"),
        18: ("soft lockup", "Soft lockup detected"),
        19: ("hard lockup", "Hard lockup detected"),
        20: ("BRK exception", "BUG/Breakpoint occurred"),
        21: ("kernel live patch", "Kernel was live-patched"),
    }
    for bit in range(26):
        if bits & (1 << bit):
            name, desc = taint_map.get(bit, (f"bit {bit}", "Unknown taint flag"))
            reasons.append(f"Bit {bit}: {name} — {desc}")
    return reasons


DANGEROUS_BOOT_PARAMS = ["mitigations=off", "pti=off", "nospec", "no_stf_barrier",
                         "nosmap", "nosmep", "nopti", "kasan=n",
                         "module.sig_enforce=0", "acpi=off", "nmi_watchdog=0"]

SERVICE_CRITICALITY: dict[str, str] = {
    "systemd-logind": "critical", "NetworkManager": "critical",
    "systemd-udevd": "critical", "display-manager": "critical",
    "gdm": "critical", "sddm": "critical", "lightdm": "critical",
    "bluetooth": "medium", "cups": "medium", "avahi-daemon": "medium",
    "systemd-resolved": "high", "systemd-networkd": "high",
    "systemd-timedated": "low", "systemd-hostnamed": "low",
    "systemd-localed": "low", "tracker": "optional",
    "tracker-miner": "optional", "packagekit": "optional",
}
SERVICE_CRITICALITY_DEFAULT = "medium"

KNOWN_EXPECTED = {
    "nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm",
    "vboxdrv", "vboxnetadp", "vboxnetflt", "vboxpci",
    "zfs", "spl", "vhba", "r8168", "dkms",
}

FINDING_EXPLANATIONS = {
    "aslr": {
        "description": "Address Space Layout Randomization randomizes memory addresses to prevent exploitation of memory corruption bugs.",
        "who_should_fix": "Everyone. Servers should have ASLR enabled at all times. Desktops and laptops benefit equally.",
        "consequence": "Without ASLR, an attacker can predict memory addresses, making buffer overflow and ROP attacks significantly easier.",
    },
    "ptrace": {
        "description": "ptrace scope controls which processes can debug (ptrace) other processes. When unrestricted, any process can attach to any other.",
        "who_should_fix": "Desktop users benefit most. Servers should also restrict it but may need it unset for certain debugging tools.",
        "consequence": "A compromised process can steal credentials, inject code, or spy on any other process running as the same user.",
    },
    "kptr": {
        "description": "kptr_restrict controls whether kernel pointers are visible in /proc filesystem interfaces.",
        "who_should_fix": "Recommended for all systems. Desktop users enabling it may notice no difference.",
        "consequence": "Exposed kernel pointers provide critical information to attackers developing exploits.",
    },
    "dmesg": {
        "description": "dmesg_restrict controls which users can read kernel log messages through the dmesg command.",
        "who_should_fix": "Servers and multi-user systems should enable this. Single-user desktops have limited benefit.",
        "consequence": "Kernel logs may contain addresses, hardware information, and driver details useful to attackers.",
    },
    "kexec": {
        "description": "kexec allows booting a new kernel from the running system without a full reboot.",
        "who_should_fix": "Servers in secure environments should disable this. Desktop power users may rely on it for kernel testing.",
        "consequence": "An attacker with root can replace the running kernel with an unsigned/untrusted kernel without triggering boot security measures.",
    },
    "taint": {
        "description": "The kernel taint flag indicates that an untrusted or out-of-tree module has been loaded, or a kernel problem has occurred.",
        "who_should_fix": "Usually no action needed on desktop systems with NVIDIA/ZFS drivers. Servers requiring Secure Boot should address this.",
        "consequence": "Tainted kernels are marked as 'unsupported' by kernel developers for bug reporting purposes. Functionality is unaffected.",
    },
    "apparmor": {
        "description": "AppArmor provides mandatory access control by confining programs to limited profiles.",
        "who_should_fix": "Servers benefit significantly. Desktop users and gamers usually don't need it.",
        "consequence": "Without AppArmor, a compromised application has access to all user files. With AppArmor, its damage is limited to its profile.",
    },
}


class KernelCheckCollector(BaseCollector):
    name = "kernel"
    tier = "standard"

    def __init__(self) -> None:
        self._loaded_modules: list[str] = []
        self._is_desktop = self._detect_desktop()

    def _detect_desktop(self) -> bool:
        try:
            output = run_cmd(["systemctl", "get-default"], timeout=5)
            return output is not None and "graphical" in output
        except Exception:
            return True

    def _has_gpu(self, vendor: str) -> bool:
        try:
            output = run_cmd(["lspci"], timeout=10)
            return output is not None and vendor in output
        except Exception:
            return False

    def _get_explanation(self, key: str) -> dict:
        return FINDING_EXPLANATIONS.get(key, {})

    def _make_finding(self, key: str, title: str, detail: str, severity: str,
                      evidence: dict | None = None, suggestion: str = "",
                      expected: bool = False, impact: str = "medium",
                      confidence: int = 100, fixable: bool = True,
                      risk: str = "safe", category: str = "kernel") -> Finding:
        exp = self._get_explanation(key)
        evidence = evidence or {}
        if exp:
            evidence["description"] = exp.get("description", "")
            evidence["who_should_fix"] = exp.get("who_should_fix", "")
            evidence["consequence"] = exp.get("consequence", "")
        return Finding(
            module=f"kernel.{key}", title=title, detail=detail,
            severity=severity, evidence=evidence, suggestion=suggestion,
            expected=expected, impact=impact, confidence=confidence,
            fixable=fixable, risk=risk, category=category,
        )

    def collect(self) -> list[Finding]:
        findings: list[Finding] = []

        result = run_cmd(["lsmod"], timeout=5)
        if result:
            self._loaded_modules = [l.split()[0] for l in result.splitlines()[1:] if l.strip()]

        has_nvidia = self._has_gpu("NVIDIA")
        is_laptop = Path("/sys/class/power_supply").exists() and any(
            d.name.startswith("BAT") for d in Path("/sys/class/power_supply").iterdir()
        )

        vm = _read_sys("/proc/sys/kernel/randomize_va_space")
        if vm is not None:
            vm_i = int(vm)
            if vm_i == 0:
                findings.append(self._make_finding("aslr", "ASLR disabled",
                    "randomize_va_space is 0. ASLR is completely disabled.",
                    "critical", evidence={"randomize_va_space": vm},
                    suggestion="Set kernel.randomize_va_space=2 in /etc/sysctl.d/99-aslr.conf",
                    impact="critical", confidence=100, fixable=True, risk="safe"))
            elif vm_i == 1:
                findings.append(self._make_finding("aslr", "ASLR partially enabled",
                    "randomize_va_space is 1 (partial). Stack is randomized but heap is not.",
                    "info", evidence={"randomize_va_space": vm},
                    suggestion="Set kernel.randomize_va_space=2 for full ASLR",
                    impact="low", confidence=100, fixable=True, risk="safe"))

        ptrace = _read_sys("/proc/sys/kernel/yama/ptrace_scope")
        if ptrace is not None:
            pt_i = int(ptrace)
            if pt_i == 0:
                findings.append(self._make_finding("ptrace", "Ptrace unrestricted",
                    "ptrace_scope=0: any process can ptrace any other process.",
                    "warning", evidence={"ptrace_scope": ptrace},
                    suggestion="Set kernel.yama.ptrace_scope=1 in /etc/sysctl.d/99-ptrace.conf",
                    impact="medium", confidence=100, fixable=True, risk="safe"))

        kptr = _read_sys("/proc/sys/kernel/kptr_restrict")
        if kptr is not None:
            kptr_i = int(kptr)
            if kptr_i == 0:
                findings.append(self._make_finding("kptr", "Kernel pointers exposed",
                    "kptr_restrict=0: kernel pointers visible to all users.",
                    "info", evidence={"kptr_restrict": kptr},
                    suggestion="Set kernel.kptr_restrict=2 in /etc/sysctl.d/99-kptr.conf",
                    impact="low", confidence=100, fixable=True, risk="safe"))

        dmesg_restrict = _read_sys("/proc/sys/kernel/dmesg_restrict")
        if dmesg_restrict is not None:
            dr_i = int(dmesg_restrict)
            if dr_i == 0:
                findings.append(self._make_finding("dmesg", "dmesg unrestricted",
                    "dmesg_restrict=0: all users can read kernel logs.",
                    "info", evidence={"dmesg_restrict": dmesg_restrict},
                    suggestion="Set kernel.dmesg_restrict=1 in /etc/sysctl.d/99-dmesg.conf",
                    impact="low", confidence=100, fixable=True, risk="safe"))

        kexec = _read_sys("/proc/sys/kernel/kexec_disabled")
        if kexec is not None:
            ke_i = int(kexec)
            if ke_i == 0:
                findings.append(self._make_finding("kexec", "Kexec not disabled",
                    "kexec is allowed. An attacker with root can replace the running kernel.",
                    "warning", evidence={"kexec_disabled": kexec},
                    suggestion="Set kernel.kexec_disabled=1 in /etc/sysctl.d/99-kexec.conf",
                    impact="medium", confidence=100, fixable=True, risk="safe"))

        tainted = _read_sys("/proc/sys/kernel/tainted")
        if tainted is not None:
            taint_val = int(tainted)
            if taint_val != 0:
                reasons = _decode_taint(taint_val)
                has_proprietary = any("proprietary" in r for r in reasons)
                has_oops = any("oops" in r or "lockup" in r or "BRK" in r for r in reasons)
                expected = has_proprietary and not has_oops
                sev = "info" if expected else "warning" if has_proprietary else "critical"
                impact = "low" if expected else "medium" if has_proprietary else "high"
                findings.append(self._make_finding("taint", "Kernel is tainted",
                    "; ".join(reasons[:3]),
                    sev, evidence={"taint_value": tainted, "reasons": reasons},
                    suggestion="No action required" if expected else "Check dmesg for details",
                    expected=expected, impact=impact, fixable=not has_proprietary,
                    risk="safe" if expected else "low"))

        vulns_dir = Path("/sys/devices/system/cpu/vulnerabilities")
        if vulns_dir.exists():
            for vuln_file in sorted(vulns_dir.iterdir()):
                try:
                    status = vuln_file.read_text().strip()
                    name = vuln_file.name.replace("_", " ").title()
                    if status.startswith("Vulnerable"):
                        findings.append(self._make_finding("cpu_vuln",
                            f"CPU vulnerability: {name}",
                            f"{name}: {status}",
                            "warning", evidence={"vulnerability": vuln_file.name, "status": status},
                            suggestion="Install latest CPU microcode and kernel update.",
                            impact="medium", confidence=90, fixable=True, risk="safe"))
                except (OSError, ValueError):
                    pass

        cmdline = _read_sys("/proc/cmdline")
        if cmdline:
            cmd_lower = cmdline.lower()
            dangerous_found = [p for p in DANGEROUS_BOOT_PARAMS if p.lower() in cmd_lower]
            if dangerous_found:
                findings.append(self._make_finding("boot_params", "Dangerous boot parameters",
                    f"Boot cmdline contains: {', '.join(dangerous_found)}",
                    "critical", evidence={"cmdline": cmdline, "dangerous_params": dangerous_found},
                    suggestion="Remove these parameters from your bootloader configuration.",
                    impact="critical", confidence=100, fixable=True, risk="moderate"))

        apparmor = _read_sys("/sys/module/apparmor/parameters/enabled")
        selinux_path = Path("/sys/fs/selinux/enforce")
        if apparmor == "N" and not selinux_path.exists():
            expected = not self._is_desktop and not is_laptop
            findings.append(self._make_finding("apparmor", "AppArmor not enabled",
                "AppArmor LSM is not active.",
                "info", evidence={"apparmor": "disabled"},
                suggestion="Install apparmor and add 'lsm=apparmor' to your kernel cmdline.",
                expected=expected, impact="low", fixable=True, risk="safe"))
        elif apparmor == "Y":
            findings.append(self._make_finding("apparmor", "AppArmor active",
                "AppArmor mandatory access control is enabled.",
                "pass", expected=True, impact="low", fixable=False, risk="safe"))

        if selinux_path.exists():
            try:
                enforce = selinux_path.read_text().strip()
                if enforce == "0":
                    findings.append(self._make_finding("selinux", "SELinux permissive",
                        "SELinux is in permissive mode (only logging, not enforcing).",
                        "warning", evidence={"selinux_enforce": "0"},
                        suggestion="Set selinux=1 in /etc/selinux/config and reboot.",
                        impact="medium", fixable=True, risk="safe"))
                elif enforce == "1":
                    findings.append(self._make_finding("selinux", "SELinux enforcing",
                        "SELinux is enforcing. Good.", "pass",
                        expected=True, impact="low", fixable=False, risk="safe"))
            except (OSError, ValueError):
                pass

        out_of_tree = [m for m in self._loaded_modules if m in KNOWN_EXPECTED]
        if out_of_tree:
            expected = all(m.startswith("nvidia") or m in ("zfs", "spl", "vboxdrv") for m in out_of_tree)
            findings.append(self._make_finding("modules", "Out-of-tree kernel modules",
                f"Loaded: {', '.join(out_of_tree)}",
                "info" if expected else "warning",
                evidence={"out_of_tree_modules": out_of_tree, "total_modules": len(self._loaded_modules)},
                suggestion="These modules are usually expected." if expected else "Investigate unexpected modules.",
                expected=expected, impact="low", fixable=False, risk="safe"))

        result = run_cmd(["dmesg", "-l", "err", "-P"], timeout=10)
        if result:
            errors = [l for l in result.splitlines() if l.strip()]
            if len(errors) > 5:
                findings.append(self._make_finding("dmesg_errors", f"Kernel errors in dmesg",
                    f"{len(errors)} kernel errors since last boot. Sample: {errors[0][:100]}",
                    "info", evidence={"dmesg_error_count": len(errors), "sample": errors[:3]},
                    suggestion="Run 'dmesg -l err' to see all kernel errors.",
                    impact="low", expected=False, fixable=False, risk="safe"))

        return findings

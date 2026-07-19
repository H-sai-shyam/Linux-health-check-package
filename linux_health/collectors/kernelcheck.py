from pathlib import Path

from linux_health.collectors.base import BaseCollector, Finding
from linux_health.utils import run_cmd, command_exists


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
        6: ("module compiled with no Version Magic", "Module version magic mismatch"),
        7: ("module compiled with different compiler", "Module was compiled with a different compiler"),
        8: ("module compiled with different compiler or version", "Same as above"),
        9: ("module uses deprecated init", "Deprecated module initialization"),
        10: ("externally built module", "External module build"),
        11: ("unsigned module", "An unsigned module was loaded"),
        12: ("module with signature verification", "Signature verification event"),
        13: ("module signature verification failed", "Signature verification failed"),
        14: ("oops occurred", "A kernel oops has occurred"),
        15: ("oops on CPU", "Kernel oops on a specific CPU"),
        16: ("machine check exception", "Hardware machine check"),
        17: ("machine check on CPU", "Machine check on a specific CPU"),
        18: ("soft lockup", "Soft lockup detected"),
        19: ("hard lockup", "Hard lockup detected"),
        20: ("BRK exception", "BUG/Breakpoint occurred"),
        21: ("kernel live patch", "Kernel was live-patched"),
        22: ("expired license", "Proprietary license expired"),
        23: ("firmware crash", "Firmware crash"),
        24: ("test taint", "Test taint (debug)"),
        25: ("unknown taint", "Unknown taint flag"),
    }
    for bit in range(26):
        if bits & (1 << bit):
            name, desc = taint_map.get(bit, (f"bit {bit}", "Unknown taint flag"))
            reasons.append(f"Bit {bit}: {name} — {desc}")
    return reasons


VULN_SEVERITY: dict[str, dict] = {
    "Vulnerable": {"severity": "warning", "suggestion": "Apply CPU microcode update or enable kernel mitigation"},
    "Mitigation: ...": {"severity": "pass", "suggestion": ""},
    "Not affected": {"severity": "pass", "suggestion": ""},
    "Unknown": {"severity": "info", "suggestion": "Check if CPU microcode is up to date"},
}

DANGEROUS_BOOT_PARAMS = ["mitigations=off", "pti=off", "nospec", "no_stf_barrier",
                         "nosmap", "nosmep", "nopti", "kasan=n",
                         "module.sig_enforce=0", "acpi=off", "nmi_watchdog=0"]


class KernelCheckCollector(BaseCollector):
    name = "kernel"
    tier = "standard"

    def collect(self) -> list[Finding]:
        findings: list[Finding] = []

        vm = _read_sys("/proc/sys/kernel/randomize_va_space")
        if vm is not None:
            vm_i = int(vm)
            if vm_i == 0:
                findings.append(Finding(module="kernel", title="ASLR disabled",
                    detail="randomize_va_space is 0. ASLR is completely disabled.",
                    severity="critical",
                    evidence={"randomize_va_space": vm},
                    suggestion="Set kernel.randomize_va_space=2 in /etc/sysctl.d/99-aslr.conf"))
            elif vm_i == 1:
                findings.append(Finding(module="kernel", title="ASLR partially enabled",
                    detail="randomize_va_space is 1 (partial). Stack is randomized but heap is not.",
                    severity="info",
                    evidence={"randomize_va_space": vm},
                    suggestion="Set kernel.randomize_va_space=2 for full ASLR"))

        ptrace = _read_sys("/proc/sys/kernel/yama/ptrace_scope")
        if ptrace is not None:
            pt_i = int(ptrace)
            if pt_i == 0:
                findings.append(Finding(module="kernel", title="Ptrace unrestricted",
                    detail="ptrace_scope=0: any process can ptrace any other process.",
                    severity="warning",
                    evidence={"ptrace_scope": ptrace},
                    suggestion="Set kernel.yama.ptrace_scope=1 in /etc/sysctl.d/99-ptrace.conf"))

        kptr = _read_sys("/proc/sys/kernel/kptr_restrict")
        if kptr is not None:
            kptr_i = int(kptr)
            if kptr_i == 0:
                findings.append(Finding(module="kernel", title="Kernel pointers exposed",
                    detail="kptr_restrict=0: kernel pointers visible to all users.",
                    severity="info",
                    evidence={"kptr_restrict": kptr},
                    suggestion="Set kernel.kptr_restrict=2 in /etc/sysctl.d/99-kptr.conf"))

        dmesg_restrict = _read_sys("/proc/sys/kernel/dmesg_restrict")
        if dmesg_restrict is not None:
            dr_i = int(dmesg_restrict)
            if dr_i == 0:
                findings.append(Finding(module="kernel", title="dmesg unrestricted",
                    detail="dmesg_restrict=0: all users can read kernel logs.",
                    severity="info",
                    evidence={"dmesg_restrict": dmesg_restrict},
                    suggestion="Set kernel.dmesg_restrict=1 in /etc/sysctl.d/99-dmesg.conf"))

        kexec = _read_sys("/proc/sys/kernel/kexec_disabled")
        if kexec is not None:
            ke_i = int(kexec)
            if ke_i == 0:
                findings.append(Finding(module="kernel", title="Kexec not disabled",
                    detail="kexec is allowed. An attacker with root can replace the running kernel.",
                    severity="warning",
                    evidence={"kexec_disabled": kexec},
                    suggestion="Set kernel.kexec_disabled=1 in /etc/sysctl.d/99-kexec.conf"))

        tainted = _read_sys("/proc/sys/kernel/tainted")
        if tainted is not None:
            taint_val = int(tainted)
            if taint_val != 0:
                reasons = _decode_taint(taint_val)
                findings.append(Finding(module="kernel", title="Kernel is tainted",
                    detail="; ".join(reasons[:3]),
                    severity="warning" if taint_val < 65536 else "critical",
                    evidence={"taint_value": tainted, "reasons": reasons},
                    suggestion="Check dmesg for details. Unsigned modules and proprietary drivers are common causes."))

        vulns_dir = Path("/sys/devices/system/cpu/vulnerabilities")
        if vulns_dir.exists():
            for vuln_file in sorted(vulns_dir.iterdir()):
                try:
                    status = vuln_file.read_text().strip()
                    name = vuln_file.name.replace("_", " ").title()
                    if status.startswith("Vulnerable"):
                        findings.append(Finding(module="kernel", title=f"CPU vulnerability: {name}",
                            detail=f"{name}: {status}",
                            severity="warning",
                            evidence={"vulnerability": vuln_file.name, "status": status},
                            suggestion="Install latest CPU microcode and kernel update."))
                    elif status.startswith("Mitigation") or status == "Not affected":
                        pass
                    elif "Unknown" in status or "Not affected" not in status:
                        findings.append(Finding(module="kernel", title=f"CPU vulnerability status unknown: {name}",
                            detail=f"{name}: {status}",
                            severity="info",
                            evidence={"vulnerability": vuln_file.name, "status": status},
                            suggestion="Update CPU microcode."))
                except (OSError, ValueError):
                    pass

        cmdline = _read_sys("/proc/cmdline")
        if cmdline:
            cmd_lower = cmdline.lower()
            dangerous_found = []
            for param in DANGEROUS_BOOT_PARAMS:
                p = param.lower()
                if p in cmd_lower:
                    dangerous_found.append(param)
            if dangerous_found:
                findings.append(Finding(module="kernel", title="Dangerous boot parameters",
                    detail=f"Boot cmdline contains: {', '.join(dangerous_found)}",
                    severity="critical",
                    evidence={"cmdline": cmdline, "dangerous_params": dangerous_found},
                    suggestion="Remove these parameters from your bootloader configuration."))

        apparmor = _read_sys("/sys/module/apparmor/parameters/enabled")
        selinux = Path("/sys/fs/selinux/enforce")
        if apparmor == "N":
            findings.append(Finding(module="kernel", title="AppArmor not enabled",
                detail="AppArmor LSM is not active.",
                severity="info",
                evidence={"apparmor": "disabled"},
                suggestion="Install apparmor and add 'lsm=apparmor' to your kernel cmdline."))
        elif apparmor == "Y":
            findings.append(Finding(module="kernel", title="AppArmor active",
                detail="AppArmor mandatory access control is enabled.",
                severity="pass"))

        if selinux.exists():
            try:
                enforce = selinux.read_text().strip()
                if enforce == "0":
                    findings.append(Finding(module="kernel", title="SELinux permissive",
                        detail="SELinux is in permissive mode (only logging, not enforcing).",
                        severity="warning",
                        evidence={"selinux_enforce": "0"},
                        suggestion="Set selinux=1 in /etc/selinux/config and reboot."))
                elif enforce == "1":
                    findings.append(Finding(module="kernel", title="SELinux enforcing",
                        detail="SELinux is enforcing. Good.",
                        severity="pass"))
            except (OSError, ValueError):
                pass

        result = run_cmd(["lsmod"], timeout=5)
        if result:
            modules = [l.split()[0] for l in result.splitlines()[1:] if l.strip()]
            known_out_of_tree = {"nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm",
                                 "vboxdrv", "vboxnetadp", "vboxnetflt", "vboxpci",
                                 "zfs", "spl", "vhba", "r8168", "dkms"}
            loaded_out_of_tree = [m for m in modules if m in known_out_of_tree]
            if loaded_out_of_tree:
                findings.append(Finding(module="kernel", title="Out-of-tree kernel modules",
                    detail=f"Loaded: {', '.join(loaded_out_of_tree)}",
                    severity="info",
                    evidence={"out_of_tree_modules": loaded_out_of_tree, "total_modules": len(modules)},
                    suggestion="These modules are not part of the mainline kernel. They may taint the kernel."))

        result = run_cmd(["dmesg", "-l", "err", "-P"], timeout=10)
        if result:
            errors = [l for l in result.splitlines() if l.strip()]
            if len(errors) > 5:
                findings.append(Finding(module="kernel", title=f"Kernel errors in dmesg",
                    detail=f"{len(errors)} kernel errors since last boot. Sample: {errors[0][:100]}",
                    severity="info",
                    evidence={"dmesg_error_count": len(errors), "sample": errors[:3]},
                    suggestion="Run 'dmesg -l err' to see all kernel errors."))

        return findings

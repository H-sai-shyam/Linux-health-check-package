import typer

from linux_health import __version__
from linux_health.battery import get_info as get_battery_info
from linux_health.boot import collect_all as get_boot_info
from linux_health.cleanup import run_cleanup
from linux_health.config import ensure_dirs
from linux_health.health import collect_all, get_doctor_recommendations
from linux_health.netdiag import collect_all as get_net_info
from linux_health.notifications import send_cleanup_notification
from linux_health.collectors.healthcheck import run_all_checks as run_health_checks
from linux_health.collectors.base import Finding
from linux_health.report import (
    console,
    show_battery_report,
    show_boot_report,
    show_cleanup_summary,
    show_dashboard,
    show_disk_analysis,
    show_doctor_results,
    show_findings_summary,
    show_help,
    show_history,
    show_net_report,
    show_security_report,
    show_sensors_report,
    show_update_report,
)
from linux_health.security import collect_all as get_security_info
from linux_health.sensors import collect_all as get_sensors_info
from linux_health.update import perform_update

app = typer.Typer(
    name="linux-health",
    help="Linux system health monitoring and maintenance utility",
    add_completion=False,
    add_help_option=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    scan: bool = typer.Option(False, "--scan", help="Only scan system, no cleanup"),
    clean: bool = typer.Option(False, "--clean", help="Run cleanup immediately"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    disk: bool = typer.Option(False, "--disk", help="Detailed disk analysis"),
    battery: bool = typer.Option(False, "--battery", help="Detailed battery report"),
    update: bool = typer.Option(False, "--update", help="Check & apply system updates"),
    net: bool = typer.Option(False, "--net", help="Full network diagnostics"),
    security: bool = typer.Option(False, "--security", help="Security audit"),
    boot: bool = typer.Option(False, "--boot", help="Boot & kernel analysis"),
    sensors: bool = typer.Option(False, "--sensors", help="Hardware sensor readout"),
    kernel: bool = typer.Option(False, "--kernel", help="Deep kernel-level analysis"),
    malware: bool = typer.Option(False, "--malware", help="Malware and rootkit scan"),
    restore: str | None = typer.Option(None, "--restore", help="Restore a cleanup snapshot by ID"),
    purge_trash: bool = typer.Option(False, "--purge-trash", help="Permanently delete all rollback snapshots"),
    history: bool = typer.Option(False, "--history", help="Show cleanup history"),
    doctor: bool = typer.Option(False, "--doctor", help="Run diagnostics"),
    help_flag: bool = typer.Option(False, "--help", help="Show this help and exit"),
    version: bool = typer.Option(False, "--version", help="Show version"),
) -> None:
    ensure_dirs()

    if help_flag:
        show_help()
        raise typer.Exit()

    if version:
        console.print(f"linux-health v{__version__}")
        raise typer.Exit()

    if history:
        show_history()
        raise typer.Exit()

    if disk:
        data = collect_all()
        da = data.get("disk_analysis", {})
        disk_findings = []
        usage = da.get("usage")
        if usage:
            pct = usage.get("percent", 0)
            if pct >= 90:
                disk_findings.append(Finding(module="disk", title="Disk critical",
                    detail=f"Disk is {pct:.0f}% full. Only {usage.get('free_h', 'N/A')} remaining.",
                    severity="critical", evidence={"usage_pct": pct}, suggestion="Free up space immediately."))
            elif pct >= 80:
                disk_findings.append(Finding(module="disk", title="Disk near full",
                    detail=f"Disk is {pct:.0f}% full. Free: {usage.get('free_h', 'N/A')}.",
                    severity="warning", evidence={"usage_pct": pct}, suggestion="Consider cleaning up."))
        mounts = da.get("mounts", [])
        if len(mounts) > 1:
            for m in mounts:
                mp = m.get("mount", "")
                mp_pct = m.get("percent", 0)
                if mp_pct > 85 and mp not in ("", "/"):
                    disk_findings.append(Finding(module="disk", title=f"Mount {mp} near full",
                        detail=f"{mp} is {mp_pct:.0f}% full.",
                        severity="info", evidence={"mount": mp, "usage_pct": mp_pct}))
        lf = da.get("largest_files", [])
        if lf:
            disk_findings.append(Finding(module="disk", title=f"Large files found",
                detail=f"Top file: {lf[0].get('path', '')[:60]} ({lf[0].get('size_h', '')})",
                severity="info", evidence={"count": len(lf)}, suggestion="Check if these files are still needed."))
        show_findings_summary(disk_findings)
        show_disk_analysis(da)
        raise typer.Exit()

    if battery:
        bat = get_battery_info()
        bat_findings = []
        if bat.get("present"):
            health = bat.get("health")
            if health is not None and health < 30:
                bat_findings.append(Finding(module="battery", title="Battery critically degraded",
                    detail=f"Battery health is {health:.0f}%. Replace soon." if health else "Health unknown.",
                    severity="critical", evidence={"health_pct": health},
                    suggestion="Replace the battery."))
            elif health is not None and health < 60:
                bat_findings.append(Finding(module="battery", title="Battery degraded",
                    detail=f"Battery health is {health:.0f}%.",
                    severity="warning", evidence={"health_pct": health},
                    suggestion="Monitor battery health and plan replacement."))
            deg = bat.get("degradation")
            if deg is not None and deg > 20:
                bat_findings.append(Finding(module="battery", title="Significant capacity lost",
                    detail=f"{deg:.0f}% of capacity lost since manufacture ({bat.get('capacity_lost_h', 'N/A')}).",
                    severity="info", evidence={"degradation": deg}))
            cycles = bat.get("cycle_count")
            if cycles is not None:
                if cycles > 800:
                    bat_findings.append(Finding(module="battery", title="High cycle count",
                        detail=f"{cycles} cycles. Nearing end of typical battery life.",
                        severity="warning", evidence={"cycles": cycles}))
                elif cycles > 500:
                    bat_findings.append(Finding(module="battery", title="Moderate cycle count",
                        detail=f"{cycles} cycles.",
                        severity="info", evidence={"cycles": cycles}))
            if bat.get("capacity") is not None and bat["capacity"] <= 15:
                bat_findings.append(Finding(module="battery", title="Battery low",
                    detail=f"Only {bat['capacity']}% charge remaining.",
                    severity="warning", evidence={"capacity_pct": bat["capacity"]},
                    suggestion="Connect the charger."))
        show_findings_summary(bat_findings)
        show_battery_report(bat)
        raise typer.Exit()

    if update:
        info = perform_update(dry_run=dry_run)
        show_update_report(info)
        raise typer.Exit()

    if net:
        info = get_net_info()
        net_findings = []
        ping_cf = info.get("ping_cloudflare", {})
        ping_gg = info.get("ping_google", {})
        if not ping_cf.get("reachable") and not ping_gg.get("reachable"):
            net_findings.append(Finding(module="network", title="No internet connectivity",
                detail="Both 1.1.1.1 and 8.8.8.8 unreachable.",
                severity="warning", evidence={}, suggestion="Check your network connection."))
        elif not ping_cf.get("reachable"):
            net_findings.append(Finding(module="network", title="Intermittent connectivity",
                detail="1.1.1.1 unreachable but 8.8.8.8 reachable.",
                severity="info", evidence={}))
        if ping_cf.get("avg_ms") and ping_cf["avg_ms"] > 200:
            net_findings.append(Finding(module="network", title="High latency",
                detail=f"Average ping {ping_cf['avg_ms']:.0f}ms to 1.1.1.1.",
                severity="info", evidence={"latency_ms": ping_cf["avg_ms"]}))
        ports = info.get("listening_ports", [])
        unknown_ports = [p for p in ports if p.get("port", "0").lstrip("*").isdigit() and int(p.get("port", "0").lstrip("*")) > 1024]
        if unknown_ports:
            port_list = ", ".join([p.get("port", "?") for p in unknown_ports[:5]])
            net_findings.append(Finding(module="network", title="Services listening on high ports",
                detail=f"Ports: {port_list}",
                severity="info", evidence={"ports": [p.get("port") for p in unknown_ports]}))
        wifi = info.get("wifi", {})
        if wifi.get("present") and wifi.get("signal_dbm") is not None:
            if wifi["signal_dbm"] < -70:
                net_findings.append(Finding(module="network", title="Weak WiFi signal",
                    detail=f"Signal: {wifi['signal_dbm']} dBm ({wifi.get('signal_quality', 'Weak')})",
                    severity="warning", evidence={"signal_dbm": wifi["signal_dbm"]},
                    suggestion="Move closer to the access point."))
        show_findings_summary(net_findings)
        show_net_report(info)
        raise typer.Exit()

    if security:
        info = get_security_info()
        show_security_report(info)
        raise typer.Exit()

    if boot:
        info = get_boot_info()
        boot_findings = []
        failed = info.get("failed_services", [])
        if failed:
            boot_findings.append(Finding(module="boot", title="Failed systemd services",
                detail=f"Services: {', '.join(failed)}",
                severity="warning", evidence={"failed_services": failed},
                suggestion=f"Run: sudo systemctl reset-failed {' '.join(failed)}"))
        errors = info.get("dmesg_errors", [])
        if errors:
            boot_findings.append(Finding(module="boot", title="Kernel errors in current boot",
                detail=f"{len(errors)} dmesg error(s) detected.",
                severity="info", evidence={"error_count": len(errors)},
                suggestion="Run 'dmesg -l err' to review."))
        old_kernels = info.get("old_kernels", [])
        if old_kernels:
            boot_findings.append(Finding(module="boot", title="Old kernels can be removed",
                detail=f"{len(old_kernels)} old kernel(s): {', '.join(old_kernels[:3])}",
                severity="info", evidence={"old_kernels": old_kernels},
                suggestion="Run: sudo pacman -R linux-<old-version>"))
        current = info.get("current_kernel", "")
        latest = info.get("latest_kernel_pkg", "")
        from linux_health.boot import is_newer_kernel_available
        if current and latest and is_newer_kernel_available(current, latest):
            boot_findings.append(Finding(module="boot", title="Kernel update available",
                detail=f"Running {current}, latest package is {latest}.",
                severity="info", evidence={"current": current, "latest": latest},
                suggestion="Update your kernel with: sudo pacman -S linux"))
        show_findings_summary(boot_findings)
        show_boot_report(info)
        raise typer.Exit()

    if sensors:
        from linux_health.collectors.hardware_scanner import HardwareScannerCollector
        from linux_health.engine.runner import run_collectors
        from linux_health.engine.scoring import calculate_score
        hw_collector = HardwareScannerCollector()
        hw_findings = run_collectors([hw_collector], tier="standard")
        hw_score = calculate_score(hw_findings)
        info = get_sensors_info()
        show_sensors_report(info, hw_findings, hw_score)
        raise typer.Exit()

    if kernel:
        from linux_health.report import show_deep_scan_results
        from linux_health.collectors.kernelcheck import KernelCheckCollector
        from linux_health.engine.runner import run_collectors
        from linux_health.engine.scoring import calculate_score
        collectors = [KernelCheckCollector()]
        findings = run_collectors(collectors, tier="standard")
        score = calculate_score(findings)
        show_deep_scan_results("Kernel Analysis", findings, score)
        raise typer.Exit()

    if malware:
        from linux_health.report import show_deep_scan_results
        from linux_health.collectors.malware import MalwareCollector
        from linux_health.engine.runner import run_collectors
        from linux_health.engine.scoring import calculate_score
        collectors = [MalwareCollector()]
        findings = run_collectors(collectors, tier="deep")
        score = calculate_score(findings)
        show_deep_scan_results("Malware Scan", findings, score)
        raise typer.Exit()

    if doctor:
        data = collect_all()
        warnings = get_doctor_recommendations(data)
        show_doctor_results(data, warnings)
        raise typer.Exit()

    if restore:
        from linux_health.trash import restore_snapshot, get_snapshots
        snaps = get_snapshots()
        snap_ids = [s.get("id") for s in snaps]
        if restore == "list":
            from linux_health.report import show_rollback_list
            show_rollback_list(snaps)
        elif restore in snap_ids:
            result = restore_snapshot(restore)
            from linux_health.report import show_restore_result
            show_restore_result(result)
        else:
            console.print(f"[red]Snapshot '{restore}' not found. Run 'lh --restore list' to see available snapshots.[/]")
        raise typer.Exit()

    if purge_trash:
        from linux_health.trash import purge_trash
        result = purge_trash()
        console.print(f"[yellow]Purged {result.get('purged', 0)} snapshot(s), freed {result.get('freed_h', '0B')}[/]")
        raise typer.Exit()

    if clean:
        summary = run_cleanup(dry_run=dry_run, rollback=True)
        show_cleanup_summary(summary)
        if not dry_run and summary.get("total_freed", 0) > 0:
            from linux_health.config import load_config
            config = load_config()
            if config.get("notifications"):
                send_cleanup_notification(summary.get("total_freed", 0))
        raise typer.Exit()

    data = collect_all()
    warnings = get_doctor_recommendations(data)
    show_dashboard(data, None, warnings)

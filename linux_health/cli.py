import typer

from linux_health import __version__
from linux_health.battery import get_info as get_battery_info
from linux_health.boot import collect_all as get_boot_info
from linux_health.cleanup import run_cleanup
from linux_health.config import ensure_dirs
from linux_health.health import collect_all, get_doctor_recommendations
from linux_health.netdiag import collect_all as get_net_info
from linux_health.notifications import send_cleanup_notification
from linux_health.report import (
    console,
    show_battery_report,
    show_boot_report,
    show_cleanup_summary,
    show_dashboard,
    show_disk_analysis,
    show_doctor_results,
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
        show_disk_analysis(data.get("disk_analysis", {}))
        raise typer.Exit()

    if battery:
        bat = get_battery_info()
        show_battery_report(bat)
        raise typer.Exit()

    if update:
        info = perform_update(dry_run=dry_run)
        show_update_report(info)
        raise typer.Exit()

    if net:
        info = get_net_info()
        show_net_report(info)
        raise typer.Exit()

    if security:
        info = get_security_info()
        show_security_report(info)
        raise typer.Exit()

    if boot:
        info = get_boot_info()
        show_boot_report(info)
        raise typer.Exit()

    if sensors:
        info = get_sensors_info()
        show_sensors_report(info)
        raise typer.Exit()

    if doctor:
        data = collect_all()
        warnings = get_doctor_recommendations(data)
        show_doctor_results(data, warnings)
        raise typer.Exit()

    if clean:
        summary = run_cleanup(dry_run=dry_run)
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

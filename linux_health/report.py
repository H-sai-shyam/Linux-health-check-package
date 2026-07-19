from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def fmt_temp(temp: float | None) -> str:
    if temp is None:
        return "N/A"
    return f"{temp:.0f}°C"


def fmt_usage_bar(percent: float, width: int = 12) -> str:
    filled = int((percent / 100) * width)
    filled = min(filled, width)
    bar = "█" * filled + "░" * (width - filled)
    return bar


def show_dashboard(data: dict, cleanup_summary: dict | None = None,
                   warnings: list | None = None) -> None:
    header = Panel(
        Text(" Linux Health ", style="bold green", justify="center"),
        box=box.HEAVY,
        border_style="green",
    )
    console.print()
    console.print(header)
    console.print()

    health_check = data.get("health_check")
    if health_check:
        overall = health_check.get("overall_score", 100)
        counts = health_check.get("severity_counts", {})
        cat_scores = health_check.get("category_scores", {})
        bar = fmt_usage_bar(overall)
        color = "green" if overall >= 80 else "yellow" if overall >= 50 else "red"
        h_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        h_table.add_column("Key", style="bold yellow")
        h_table.add_column("Value")
        h_table.add_row("Overall", f"[bold {color}]{bar}  {overall:.0f}/100[/]")
        h_table.add_row("Critical", f"[red]{counts.get('critical', 0)}[/]")
        h_table.add_row("Warnings", f"[yellow]{counts.get('warning', 0)}[/]")
        h_table.add_row("Info", f"[cyan]{counts.get('info', 0)}[/]")
        if cat_scores:
            cats = "  ".join(f"{k}: [bold]{v:.0f}[/]" for k, v in sorted(cat_scores.items()))
            h_table.add_row("Per category", cats)
        console.print(Panel(h_table, title="[bold]HEALTH SCORE[/]", border_style=color))
        console.print()

    sys = data.get("system", {})
    s_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    s_table.add_column("Key", style="bold yellow")
    s_table.add_column("Value")
    s_table.add_row("Hostname", sys.get("hostname", "N/A"))
    s_table.add_row("OS", sys.get("os", "N/A"))
    s_table.add_row("Kernel", sys.get("kernel", "N/A"))
    s_table.add_row("Uptime", sys.get("uptime", "N/A"))
    console.print(Panel(s_table, title="[bold]SYSTEM[/]", border_style="blue"))
    console.print()

    cpu_info = data.get("cpu", {})
    c_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    c_table.add_column("Key", style="bold yellow")
    c_table.add_column("Value")
    cpu_temp = data.get("cpu_temp")
    c_table.add_row("Usage", f"{cpu_info.get('usage', 0):.0f}%")
    c_table.add_row("Temperature", fmt_temp(cpu_temp))
    console.print(Panel(c_table, title="[bold]CPU[/]", border_style="blue"))
    console.print()

    ram = data.get("ram", {})
    m_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    m_table.add_column("Key", style="bold yellow")
    m_table.add_column("Value")
    m_table.add_row("RAM", f"{ram.get('used_h', 'N/A')} / {ram.get('total_h', 'N/A')}")
    m_table.add_row("Usage", f"{ram.get('percent', 0):.0f}%")
    console.print(Panel(m_table, title="[bold]MEMORY[/]", border_style="blue"))
    console.print()

    swap = data.get("swap", {})
    sw_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    sw_table.add_column("Key", style="bold yellow")
    sw_table.add_column("Value")
    sw_table.add_row("Usage", f"{swap.get('percent', 0):.0f}%")
    console.print(Panel(sw_table, title="[bold]SWAP[/]", border_style="blue"))
    console.print()

    battery_info = data.get("battery", {})
    if battery_info.get("present"):
        b_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        b_table.add_column("Key", style="bold yellow")
        b_table.add_column("Value")
        b_table.add_row("Charge", battery_info.get("capacity_h") or "N/A")
        b_table.add_row("Health", battery_info.get("health_h") or "N/A")
        if battery_info.get("cycle_count") is not None:
            b_table.add_row("Cycles", str(battery_info["cycle_count"]))
        b_table.add_row("Status", battery_info.get("status", "N/A"))
        time_h = battery_info.get("time_remaining_h")
        if time_h:
            label = battery_info.get("time_remaining_label", "Time")
            b_table.add_row(label, time_h)
        console.print(Panel(b_table, title="[bold]BATTERY[/]", border_style="blue"))
        console.print()

    disk_info = data.get("disk")
    if disk_info:
        pct = disk_info.get("percent", 0)
        bar = fmt_usage_bar(pct)
        d_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        d_table.add_column("Key", style="bold yellow")
        d_table.add_column("Value")
        d_table.add_row("Mount", disk_info.get("mount", "/"))
        d_table.add_row("Total", disk_info.get("total_h", "N/A"))
        d_table.add_row("Used", disk_info.get("used_h", "N/A"))
        d_table.add_row("Free", disk_info.get("free_h", "N/A"))
        d_table.add_row("Usage", f"{bar}  {pct:.0f}%")
        console.print(Panel(d_table, title="[bold]STORAGE[/]", border_style="blue"))
        console.print()

    common_dirs = (data.get("disk_analysis") or {}).get("common_dirs", [])
    if common_dirs:
        top = [d for d in common_dirs if d["size"] > 100 * 1024 * 1024][:6]
        if top:
            cd_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
            cd_table.add_column("Directory", style="bold yellow")
            cd_table.add_column("Size")
            for d in top:
                cd_table.add_row(d.get("name", ""), d.get("size_h", ""))
            console.print(Panel(cd_table, title="[bold]TOP DIRECTORIES[/]", border_style="blue"))
            console.print()

    cache = data.get("cache", {})
    if cache:
        ca_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        ca_table.add_column("Key", style="bold yellow")
        ca_table.add_column("Value")
        ca_table.add_row("User cache", cache.get("user_cache_h", "N/A"))
        ca_table.add_row("Pacman cache", cache.get("pacman_h", "N/A"))
        ca_table.add_row("Flatpak", cache.get("flatpak_h", "N/A"))
        console.print(Panel(ca_table, title="[bold]CACHE[/]", border_style="blue"))
        console.print()

    dev = data.get("dev", {})
    if dev:
        dv_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        dv_table.add_column("Key", style="bold yellow")
        dv_table.add_column("Value")
        dv_table.add_row("Maven", dev.get("maven_h", "N/A"))
        dv_table.add_row("Gradle", dev.get("gradle_h", "N/A"))
        console.print(Panel(dv_table, title="[bold]DEVELOPMENT[/]", border_style="blue"))
        console.print()

    if warnings:
        w_table = Table(show_header=True, box=box.SIMPLE)
        w_table.add_column("Severity", style="bold")
        w_table.add_column("Message")
        for w in warnings:
            sev_style = {"critical": "bold red", "warning": "yellow", "info": "cyan"}
            w_table.add_row(
                w.get("severity", "info").upper(),
                w.get("message", ""),
                style=sev_style.get(w.get("severity", "info"), ""),
            )
        console.print(Panel(w_table, title="[bold]WARNINGS[/]", border_style="red"))
        console.print()

    if cleanup_summary:
        footer = Panel(
            Text(
                f"Last cleanup: {data.get('last_cleanup', 'Never')}   |   "
                f"Next cleanup: {data.get('next_cleanup', 'Today')}",
                style="bold cyan",
            ),
            box=box.HEAVY,
            border_style="green",
        )
    else:
        footer = Panel(
            Text(
                f"Last cleanup: {data.get('last_cleanup', 'Never')}   |   "
                f"Next cleanup: {data.get('next_cleanup', 'Today')}",
                style="bold cyan",
            ),
            box=box.HEAVY,
            border_style="green",
        )
    console.print(footer)


def show_disk_analysis(analysis: dict) -> None:
    usage = analysis.get("usage")
    if usage:
        pct = usage.get("percent", 0)
        bar = fmt_usage_bar(pct)
        d_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        d_table.add_column("Key", style="bold yellow")
        d_table.add_column("Value")
        d_table.add_row("Mount", usage.get("mount", "/"))
        d_table.add_row("Total", usage.get("total_h", "N/A"))
        d_table.add_row("Used", usage.get("used_h", "N/A"))
        d_table.add_row("Free", usage.get("free_h", "N/A"))
        d_table.add_row("Usage", f"{bar}  {pct:.0f}%")
        console.print(Panel(d_table, title="[bold]DISK USAGE[/]", border_style="blue"))
        console.print()

    mounts = analysis.get("mounts", [])
    if len(mounts) > 1:
        m_table = Table(title="Mount Points", box=box.SIMPLE)
        m_table.add_column("Mount", style="bold")
        m_table.add_column("Total")
        m_table.add_column("Used")
        m_table.add_column("Free")
        m_table.add_column("Use%")
        for m in mounts:
            mp = m.get("mount", "")
            p = m.get("percent", 0)
            m_table.add_row(
                mp, m.get("total_h", ""), m.get("used_h", ""),
                m.get("free_h", ""), f"{p:.0f}%",
            )
        console.print(m_table)
        console.print()

    common = analysis.get("common_dirs", [])
    if common:
        c_table = Table(
            title="Directory Breakdown",
            box=box.SIMPLE,
        )
        c_table.add_column("Directory", style="bold")
        c_table.add_column("Size", style="green")
        c_table.add_column("% of Disk")
        total = (usage or {}).get("total", 1)
        for d in common:
            pct_of_disk = (d["size"] / total) * 100 if total else 0
            c_table.add_row(
                d.get("name", ""),
                d.get("size_h", ""),
                f"{pct_of_disk:.1f}%",
            )
        console.print(c_table)
        console.print()

    largest_dirs = analysis.get("largest_dirs", [])
    if largest_dirs:
        ld_table = Table(title=f"Largest Directories (>{'100MB'})", box=box.SIMPLE)
        ld_table.add_column("#", style="dim")
        ld_table.add_column("Path", style="bold")
        ld_table.add_column("Size", style="green")
        for i, d in enumerate(largest_dirs, 1):
            ld_table.add_row(str(i), d.get("path", ""), d.get("size_h", ""))
        console.print(ld_table)
        console.print()

    largest_files = analysis.get("largest_files", [])
    if largest_files:
        lf_table = Table(title=f"Largest Files (>{'100MB'})", box=box.SIMPLE)
        lf_table.add_column("#", style="dim")
        lf_table.add_column("File", style="bold")
        lf_table.add_column("Size", style="green")
        for i, f in enumerate(largest_files, 1):
            lf_table.add_row(str(i), f.get("path", ""), f.get("size_h", ""))
        console.print(lf_table)
        console.print()


def show_battery_report(bat: dict) -> None:
    if not bat.get("present"):
        console.print("[yellow]No battery detected.[/]")
        return

    header = Panel(
        Text(" Battery Report ", style="bold green", justify="center"),
        box=box.HEAVY,
        border_style="green",
    )
    console.print()
    console.print(header)
    console.print()

    cap = bat.get("capacity")
    if cap is not None:
        bar = fmt_usage_bar(cap)
        c_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        c_table.add_column("Key", style="bold yellow")
        c_table.add_column("Value")
        c_table.add_row("Level", f"{bar}  {cap}%")
        c_table.add_row("Status", bat.get("status", "N/A"))
        c_table.add_row("Capacity Level", bat.get("capacity_level", "N/A"))
        time_h = bat.get("time_remaining_h")
        if time_h:
            label = bat.get("time_remaining_label", "Time")
            c_table.add_row(label, time_h)
        console.print(Panel(c_table, title="[bold]CHARGE[/]", border_style="blue"))
        console.print()

    d_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    d_table.add_column("Key", style="bold yellow")
    d_table.add_column("Value")

    health = bat.get("health")
    if health is not None:
        health_bar = fmt_usage_bar(health)
        d_table.add_row("Health", f"{health_bar}  {health}%")
    deg = bat.get("degradation")
    if deg is not None:
        d_table.add_row("Degradation", f"[red]{deg}%[/]")
    lost = bat.get("capacity_lost_h")
    if lost:
        d_table.add_row("Capacity lost", lost)
    if bat.get("cycle_count") is not None:
        d_table.add_row("Cycle count", str(bat["cycle_count"]))

    d_table.add_row("Technology", bat.get("technology", "N/A"))

    if bat.get("manufacturer"):
        d_table.add_row("Manufacturer", bat["manufacturer"])
    if bat.get("model_name"):
        d_table.add_row("Model", bat["model_name"])
    if bat.get("serial_number"):
        d_table.add_row("Serial", bat["serial_number"])
    if bat.get("temperature") is not None:
        d_table.add_row("Temperature", f"{bat['temperature']}°C")

    console.print(Panel(d_table, title="[bold]HEALTH & INFO[/]", border_style="blue"))
    console.print()

    p_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    p_table.add_column("Key", style="bold yellow")
    p_table.add_column("Value")

    if bat.get("charge_full_design_h"):
        p_table.add_row("Design capacity", bat["charge_full_design_h"])
    if bat.get("charge_full_h"):
        p_table.add_row("Current full", bat["charge_full_h"])
    if bat.get("charge_now_h"):
        p_table.add_row("Current charge", bat["charge_now_h"])
    if bat.get("voltage_now_h"):
        p_table.add_row("Voltage", bat["voltage_now_h"])
    if bat.get("voltage_min_design_h"):
        p_table.add_row("Min voltage", bat["voltage_min_design_h"])
    if bat.get("current_now_h"):
        p_table.add_row("Current", bat["current_now_h"])
    if bat.get("power_now_h"):
        p_table.add_row("Power", bat["power_now_h"])

    console.print(Panel(p_table, title="[bold]ELECTRICAL[/]", border_style="blue"))
    console.print()

    recommendations = []
    if health is not None and health < 60:
        recommendations.append("[red]⚠ Battery health critical. Consider replacement.[/]")
    elif health is not None and health < 80:
        recommendations.append("[yellow]⚠ Battery degraded. Monitor health.[/]")
    if deg is not None and deg > 20:
        recommendations.append(f"[yellow]⚠ {deg}% capacity lost since manufacture.[/]")
    if bat.get("cycle_count") is not None and bat["cycle_count"] > 500:
        recommendations.append(f"[yellow]⚠ High cycle count ({bat['cycle_count']}). Battery nearing end of life.[/]")

    if recommendations:
        console.print(Panel(
            "\n".join(recommendations),
            title="[bold]RECOMMENDATIONS[/]",
            border_style="red",
        ))
        console.print()


def show_findings_summary(findings: list, title: str = "Findings") -> None:
    if not findings:
        return
    by_severity: dict = {"critical": [], "warning": [], "info": [], "pass": []}
    for f in findings:
        by_severity.setdefault(f.severity, []).append(f)

    for sev, label, style, border in [
        ("critical", "CRITICAL", "bold red", "red"),
        ("warning", "WARNINGS", "bold yellow", "yellow"),
        ("info", "INFO", "cyan", "blue"),
        ("pass", "PASS", "green", "green"),
    ]:
        items = by_severity.get(sev, [])
        if not items:
            continue
        for f in items:
            fd_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
            fd_table.add_column("Key", style="bold yellow")
            fd_table.add_column("Value")
            fd_table.add_row("Title", f.title)
            fd_table.add_row("Detail", f.detail)
            if f.suggestion:
                fd_table.add_row("Suggestion", f"[italic]{f.suggestion}[/]")
            if f.evidence:
                for k, v in list(f.evidence.items())[:3]:
                    try:
                        fd_table.add_row(k, str(v)[:80])
                    except Exception:
                        pass
            console.print(Panel(fd_table, title=f"[{style}] {label} [/]", border_style=border))
            console.print()


def show_deep_scan_results(title: str, findings: list, score: float) -> None:
    from linux_health.collectors.base import Finding

    header = Panel(
        Text(f" {title} ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print(); console.print(header); console.print()

    color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    bar = fmt_usage_bar(score)
    console.print(f"[bold]Score:[/] [{color}]{bar}  {score:.0f}/100[/]")
    console.print()

    if not findings:
        console.print("[green]No issues found.[/]")
        console.print()
    else:
        show_findings_summary(findings)


def show_rollback_list(snapshots: list[dict]) -> None:
    if not snapshots:
        console.print("[yellow]No rollback snapshots available.[/]")
        return
    rl_table = Table(title="Rollback Snapshots", box=box.SIMPLE)
    rl_table.add_column("ID", style="bold")
    rl_table.add_column("Created")
    rl_table.add_column("Expires")
    rl_table.add_column("Size")
    rl_table.add_column("Items")
    for s in snapshots:
        si = __import__("linux_health.trash", fromlist=["snapshot_info"]).snapshot_info(s)
        rl_table.add_row(
            si.get("id", ""), si.get("created", ""), si.get("remaining", ""),
            si.get("total_size_h", ""), str(si.get("items_count", 0)),
        )
    console.print(rl_table)
    console.print("[dim]Restore with: lh --restore <snapshot-id>[/]")
    console.print()


def show_restore_result(result: dict) -> None:
    if "error" in result:
        console.print(f"[red]{result['error']}[/]")
        return
    restored = result.get("restored", 0)
    total = result.get("total", 0)
    errors = result.get("errors", [])
    if restored == total:
        console.print(f"[green]✓ Restored {restored}/{total} items from {result.get('id', 'snapshot')}[/]")
    else:
        console.print(f"[yellow]Restored {restored}/{total} items from {result.get('id', 'snapshot')}[/]")
    for e in errors:
        console.print(f"  [red]• {e}[/]")
    console.print()


def show_history() -> None:
    from linux_health.history import get_history
    history = get_history()
    if not history:
        console.print("[yellow]No cleanup history found.[/]")
        return

    h_table = Table(title="Cleanup History")
    h_table.add_column("Date", style="bold")
    h_table.add_column("Freed", style="green")
    h_table.add_column("Actions")

    for entry in history:
        h_table.add_row(
            entry.get("date", "N/A"),
            entry.get("freed_h", human_readable(entry.get("freed", 0))),
            ", ".join(entry.get("actions", [])) if entry.get("actions") else "-",
        )
    console.print(h_table)


def show_doctor_results(data: dict, warnings: list[dict]) -> None:
    sys = data.get("system", {})
    console.print(f"[bold]Host:[/] {sys.get('hostname', 'N/A')}")
    console.print(f"[bold]OS:[/] {sys.get('os', 'N/A')}")
    console.print(f"[bold]Uptime:[/] {sys.get('uptime', 'N/A')}")
    console.print()

    if not warnings:
        console.print("[green]No issues detected. System is healthy.[/]")
        return

    for w in warnings:
        sev = w.get("severity", "info")
        icon = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(sev, "ℹ️")
        style = {"critical": "bold red", "warning": "yellow", "info": "cyan"}.get(sev, "")
        console.print(f"{icon} [{style}]{w.get('message', '')}[/]")
    console.print()


def show_cleanup_summary(summary: dict) -> None:
    if summary.get("dry_run"):
        console.print("[bold yellow]DRY RUN - Nothing was deleted[/]")
        console.print()
        console.print("Would remove:")
        console.print()
    else:
        console.print("[bold green]Cleanup completed[/]")
        if summary.get("rollback") and summary.get("trash_id"):
            tid = summary["trash_id"]
            console.print(f"[bold cyan]Rollback available:[/] lh --restore {tid}")
            console.print()
        console.print()

    for name, result in summary.get("results", {}).items():
        freed = result.get("freed", 0)
        if freed > 0:
            from linux_health.utils import human_size
            console.print(f"  {name}: [green]{human_size(freed)}[/]")
        for action in result.get("actions", []):
            console.print(f"    • {action}")

    console.print()
    if summary.get("total_freed", 0) > 0 or summary.get("dry_run"):
        console.print(f"Total: [bold]{summary.get('total_freed_h', '0B')}[/]")

    if summary.get("dry_run"):
        console.print()
        console.print("[bold yellow]Nothing deleted.[/]")


def show_update_report(data: dict) -> None:
    header = Panel(
        Text(" Update Report ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print(); console.print(header); console.print()

    s_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    s_table.add_column("Check", style="bold yellow")
    s_table.add_column("Result")

    pending = data.get("pending_updates", 0)
    s_table.add_row("Pending updates", str(pending) if pending > 0 else "[green]Up to date[/]")

    partial = data.get("partial_upgrades", 0)
    if partial > 0:
        s_table.add_row("Partial upgrades", f"[red]{partial} packages with issues[/]")
    else:
        s_table.add_row("Partial upgrades", "[green]None[/]")

    orphans = data.get("pre_update_orphans", [])
    s_table.add_row("Orphaned packages", str(len(orphans)))

    held = data.get("held_packages", [])
    if held:
        s_table.add_row("Held packages", ", ".join(held[:5]))

    aur = data.get("aur_updates", {})
    if aur.get("available"):
        s_table.add_row("AUR updates", str(aur.get("count", 0)))

    console.print(Panel(s_table, title="[bold]PRE-FLIGHT CHECKS[/]", border_style="blue"))
    console.print()

    if data.get("update_done"):
        console.print("[green]✓ Update completed[/]")
        console.print()
        out = data.get("output", "")
        if out:
            console.print(Panel(out[-400:], title="[bold]UPDATE OUTPUT (tail)[/]", border_style="green"))

    services = data.get("services_needing_restart", [])
    if services:
        sv_table = Table(title="Services Possibly Needing Restart", box=box.SIMPLE)
        sv_table.add_column("Service/Issue")
        for s in services:
            sv_table.add_row(s)
        console.print(sv_table)
        console.print()


def show_net_report(data: dict) -> None:
    header = Panel(
        Text(" Network Report ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print(); console.print(header); console.print()

    i_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    i_table.add_column("Key", style="bold yellow")
    i_table.add_column("Value")
    i_table.add_row("Hostname", data.get("hostname", "N/A"))
    i_table.add_row("Public IP", data.get("public_ip", "N/A"))
    i_table.add_row("Gateway", data.get("gateway", "N/A"))
    dns = data.get("dns_servers", [])
    i_table.add_row("DNS", ", ".join(dns) if dns else "N/A")
    console.print(Panel(i_table, title="[bold]CONNECTIVITY[/]", border_style="blue"))
    console.print()

    for iface in data.get("interfaces", []):
        if_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        if_table.add_column("Key", style="bold yellow")
        if_table.add_column("Value")
        if_table.add_row("Interface", iface.get("name", ""))
        if_table.add_row("State", iface.get("state", ""))
        for ip in iface.get("ips", []):
            if_table.add_row("IP", ip)
        if iface.get("mac"):
            if_table.add_row("MAC", iface["mac"])
        if iface.get("speed"):
            if_table.add_row("Speed", iface["speed"])
        if iface.get("duplex"):
            if_table.add_row("Duplex", iface["duplex"])
        console.print(Panel(if_table, title=f"[bold]INTERFACE: {iface.get('name', '?')}[/]", border_style="blue"))
        console.print()

    wifi = data.get("wifi", {})
    if wifi.get("present"):
        w_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        w_table.add_column("Key", style="bold yellow")
        w_table.add_column("Value")
        w_table.add_row("SSID", wifi.get("ssid", "N/A"))
        w_table.add_row("Signal", wifi.get("signal_quality", "N/A"))
        if wifi.get("signal_dbm") is not None:
            w_table.add_row("RSSI", f"{wifi['signal_dbm']} dBm")
        if wifi.get("freq_mhz"):
            w_table.add_row("Frequency", f"{wifi['freq_mhz']} MHz")
        if wifi.get("bitrate"):
            w_table.add_row("Bitrate", wifi["bitrate"])
        console.print(Panel(w_table, title="[bold]WIFI[/]", border_style="blue"))
        console.print()

    ping1 = data.get("ping_cloudflare", {})
    ping2 = data.get("ping_google", {})
    p_table = Table(show_header=True, box=box.SIMPLE)
    p_table.add_column("Target")
    p_table.add_column("Reachable", style="bold")
    p_table.add_column("Avg Latency")
    p_table.add_column("Loss")
    for p in [ping1, ping2]:
        reachable = p.get("reachable", False)
        p_table.add_row(
            p.get("target", "?"),
            "[green]Yes[/]" if reachable else "[red]No[/]",
            f"{p.get('avg_ms', 'N/A')} ms" if p.get("avg_ms") else "N/A",
            f"{p.get('loss', 100)}%",
        )
    console.print(Panel(p_table, title="[bold]PING[/]", border_style="blue"))
    console.print()

    dns_r = data.get("dns_resolve", {})
    if dns_r.get("ips"):
        d_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        d_table.add_column("Key", style="bold yellow")
        d_table.add_column("Value")
        d_table.add_row("Resolved", dns_r.get("hostname", ""))
        d_table.add_row("IPs", ", ".join(dns_r["ips"]))
        d_table.add_row("Time", f"{dns_r.get('time_ms', 'N/A')} ms")
        console.print(Panel(d_table, title="[bold]DNS RESOLUTION[/]", border_style="blue"))
        console.print()

    ports = data.get("listening_ports", [])
    if ports:
        port_table = Table(title="Listening Ports", box=box.SIMPLE)
        port_table.add_column("Port", style="bold")
        port_table.add_column("Address")
        port_table.add_column("Process")
        for p in ports[:15]:
            port_table.add_row(p.get("port", ""), p.get("address", ""), p.get("process", ""))
        console.print(port_table)
        console.print()

    conns = data.get("active_connections", 0)
    console.print(f"[bold]Active connections:[/] {conns}")


def show_security_report(data: dict) -> None:
    header = Panel(
        Text(" Security Audit ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print(); console.print(header); console.print()

    ssh = data.get("failed_ssh_attempts", -1)
    if ssh >= 0:
        s = "[green]None[/]" if ssh == 0 else f"[red]{ssh} attempts in 30 days[/]"
        console.print(f"[bold]Failed SSH logins:[/] {s}")

    ports = data.get("open_ports", [])
    if ports:
        port_table = Table(title="Open Listening Ports", box=box.SIMPLE)
        port_table.add_column("Port", style="bold")
        port_table.add_column("Address")
        port_table.add_column("Process")
        for p in ports:
            port_table.add_row(str(p.get("port", "")), p.get("address", ""), p.get("process", ""))
        console.print(port_table)
    else:
        console.print("[bold]Open ports:[/] [green]None (or unable to scan)[/]")
    console.print()

    suid = data.get("suid_issues", [])
    if suid:
        console.print(f"[red]⚠ {len(suid)} SUID file(s) not owned by root:[/]")
        for s in suid[:5]:
            console.print(f"  • {s.get('path', '')}")
        console.print()

    ww = data.get("world_writable_etc", [])
    if ww:
        console.print(f"[red]⚠ {len(ww)} world-writable file(s) in /etc:[/]")
        for f in ww[:5]:
            console.print(f"  • {f}")
        console.print()

    uid0 = data.get("uid_zero_users", [])
    if uid0:
        console.print(f"[red]⚠ Non-root users with UID 0: {', '.join(uid0)}[/]")
        console.print()

    vuln = data.get("known_vulnerable", [])
    if vuln:
        v_table = Table(title="Known Vulnerable Packages (arch-audit)", box=box.SIMPLE)
        v_table.add_column("Package", style="bold red")
        for v in vuln:
            v_table.add_row(v)
        console.print(v_table)
        console.print()
    else:
        console.print("[bold]Known vulnerabilities:[/] [green]None detected[/]")

    timers = data.get("recent_timers", [])
    cron = data.get("recent_cron", [])
    if timers or cron:
        console.print("[bold yellow]Recently modified scheduled tasks (7 days):[/]")
        for t in timers:
            console.print(f"  • {t.get('path', '')}")
        for c in cron:
            console.print(f"  • {c}")
        console.print()


def show_boot_report(data: dict) -> None:
    header = Panel(
        Text(" Boot & Kernel Report ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print(); console.print(header); console.print()

    k_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    k_table.add_column("Key", style="bold yellow")
    k_table.add_column("Value")
    k_table.add_row("Running kernel", data.get("current_kernel", "N/A"))
    k_table.add_row("Latest kernel pkg", data.get("latest_kernel_pkg", "N/A"))
    console.print(Panel(k_table, title="[bold]KERNEL[/]", border_style="blue"))
    console.print()

    kernels = data.get("installed_kernels", [])
    if kernels:
        ke_table = Table(title="Installed Kernels", box=box.SIMPLE)
        ke_table.add_column("Kernel", style="bold")
        ke_table.add_column("Size")
        ke_table.add_column("Status")
        current = data.get("current_kernel", "")
        for k in kernels:
            status = "[green]Running[/]" if current and current.startswith(k["version"]) else "[yellow]Old[/]"
            ke_table.add_row(k["version"], k.get("size_h", ""), status)
        console.print(ke_table)
        console.print()

    old = data.get("old_kernels", [])
    if old:
        console.print(f"[yellow]Old kernels that can be removed: {', '.join(old)}[/]")
        console.print()

    boot = data.get("boot_usage")
    if boot:
        b_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        b_table.add_column("Key", style="bold yellow")
        b_table.add_column("Value")
        bar = fmt_usage_bar(boot.get("percent", 0))
        b_table.add_row("Usage", f"{bar}  {boot.get('percent', 0):.0f}%")
        b_table.add_row("Used", boot.get("used_h", ""))
        b_table.add_row("Free", boot.get("free_h", ""))
        console.print(Panel(b_table, title="[bold]/BOOT USAGE[/]", border_style="blue"))
        console.print()

    grub = data.get("grub_config")
    if grub:
        g_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        g_table.add_column("Key", style="bold yellow")
        g_table.add_column("Value")
        if grub.get("default"):
            g_table.add_row("Default", grub["default"])
        if grub.get("timeout"):
            g_table.add_row("Timeout", f"{grub['timeout']}s")
        if grub.get("cmdline"):
            g_table.add_row("Cmdline", grub["cmdline"])
        console.print(Panel(g_table, title="[bold]GRUB[/]", border_style="blue"))
        console.print()

    btime = data.get("boot_time")
    if btime:
        console.print(f"[bold]Boot time:[/] {btime}")
        console.print()

    blame = data.get("blame", [])
    if blame:
        bl_table = Table(title="Slowest Services (systemd-analyze blame)", box=box.SIMPLE)
        bl_table.add_column("Time", style="bold")
        bl_table.add_column("Unit")
        for b in blame[:8]:
            bl_table.add_row(b.get("time", ""), b.get("unit", ""))
        console.print(bl_table)
        console.print()

    failed = data.get("failed_services", [])
    if failed:
        console.print(f"[red]⚠ Failed services: {', '.join(failed)}[/]")
        console.print()

    errors = data.get("dmesg_errors", [])
    if errors:
        err_table = Table(title="Recent dmesg Errors (last 20)", box=box.SIMPLE)
        err_table.add_column("Error", style="red")
        for e in errors[-8:]:
            err_table.add_row(e[:100])
        console.print(err_table)
        console.print()


def show_sensors_report(data: dict, hw_findings: list | None = None, hw_score: float | None = None) -> None:
    header = Panel(
        Text(" Sensors Report ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print(); console.print(header); console.print()

    if hw_findings and hw_score is not None:
        color = "green" if hw_score >= 80 else "yellow" if hw_score >= 50 else "red"
        bar = fmt_usage_bar(hw_score)
        console.print(f"[bold]Hardware Condition:[/] [{color}]{bar}  {hw_score:.0f}%[/]")
        console.print()
        show_findings_summary(hw_findings)

    cpu_temps = data.get("cpu_temps", [])
    if cpu_temps:
        ct_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        ct_table.add_column("Sensor", style="bold yellow")
        ct_table.add_column("Temp")
        for c in cpu_temps:
            ct_table.add_row(c.get("type", "?"), f"{c.get('temp', 0):.1f}°C")
        console.print(Panel(ct_table, title="[bold]CPU TEMPERATURES[/]", border_style="blue"))
        console.print()

    gpus = data.get("gpus", [])
    if gpus:
        for gpu in gpus:
            g_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
            g_table.add_column("Key", style="bold yellow")
            g_table.add_column("Value")
            g_table.add_row("Vendor", gpu.get("vendor", ""))
            g_table.add_row("Model", gpu.get("name", ""))
            if gpu.get("temp") is not None:
                g_table.add_row("Temp", f"{gpu['temp']:.0f}°C")
            if gpu.get("usage") is not None:
                g_table.add_row("Usage", f"{gpu['usage']:.0f}%")
            if gpu.get("power_w") is not None:
                g_table.add_row("Power", f"{gpu['power_w']:.1f}W")
            console.print(Panel(g_table, title=f"[bold]GPU: {gpu.get('name', gpu.get('vendor', '?'))}[/]", border_style="blue"))
            console.print()

    fans = data.get("fans", [])
    if fans:
        f_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        f_table.add_column("Fan", style="bold yellow")
        f_table.add_column("Speed")
        for fan in fans:
            f_table.add_row(fan.get("label", "?"), f"{fan.get('speed_rpm', 0)} RPM")
        console.print(Panel(f_table, title="[bold]FAN SPEEDS[/]", border_style="blue"))
        console.print()

    disks = data.get("disk_temps", [])
    if disks:
        d_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        d_table.add_column("Device", style="bold yellow")
        d_table.add_column("Type")
        d_table.add_column("Temp")
        for disk in disks:
            d_table.add_row(disk.get("device", ""), disk.get("type", ""), f"{disk.get('temp', 0):.0f}°C")
        console.print(Panel(d_table, title="[bold]DISK TEMPERATURES[/]", border_style="blue"))
        console.print()

    bat_temp = data.get("battery_temp")
    if bat_temp is not None:
        console.print(f"[bold]Battery temp:[/] {bat_temp:.0f}°C")
        console.print()

    power = data.get("power", [])
    if power:
        p_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        p_table.add_column("Domain", style="bold yellow")
        p_table.add_column("Energy (µJ)")
        for p in power[:5]:
            p_table.add_row(p.get("domain", "?"), f"{p.get('energy_uj', 0):,}")
        console.print(Panel(p_table, title="[bold]POWER CONSUMPTION[/]", border_style="blue"))
        console.print()


def show_help() -> None:
    from linux_health import __version__

    header = Panel(
        Text(" Linux Health ", style="bold green", justify="center"),
        box=box.HEAVY, border_style="green",
    )
    console.print()
    console.print(header)
    console.print()
    console.print(f"  Version: [bold cyan]{__version__}[/]")
    console.print(f"  Alias:   [bold]lh[/]  (symlink in ~/.local/bin)")
    console.print()

    console.print(Panel(
        "A lightweight native Linux system health monitoring and maintenance utility.\n"
        "One command to see the complete health state of your system.\n"
        "Automatic weekly maintenance via systemd timer.",
        title="[bold]About[/]", border_style="blue",
    ))
    console.print()

    overview = Panel(
        "[bold]lh[/] — Dashboard (default, no flag needed)\n"
        "   Shows system info, CPU, memory, swap, battery,\n"
        "   storage, cache, development dirs, warnings, and\n"
        "   last/next cleanup schedule.",
        title="[bold]OVERVIEW[/]", border_style="green",
    )
    console.print(overview)
    console.print()

    diag_table = Table(title="Diagnostics & Reports", box=box.SIMPLE)
    diag_table.add_column("Command", style="bold yellow", width=20)
    diag_table.add_column("What it does")
    diag_table.add_row("[bold]lh[/]",   "Complete system dashboard\nwith health score, kernel & malware findings")
    diag_table.add_row("[bold]lh --scan[/]",   "Scan only, no cleanup")
    diag_table.add_row("[bold]lh --doctor[/]", "Run diagnostics & recommendations")
    diag_table.add_row("[bold]lh --disk[/]",   "Detailed disk analysis:\nlargest dirs, largest files,\ndirectory breakdown, all mount points")
    diag_table.add_row("[bold]lh --battery[/]",   "Detailed battery report:\nhealth %, degradation %, capacity lost,\ntime remaining, cycles, voltage, power,\ntemperature, manufacturer, recommendations")
    diag_table.add_row("[bold]lh --update[/]",   "System update with safety checks:\npending updates, partial upgrades,\norphaned packages, held packages,\nAUR updates, then pacman -Syu\n+ post-update service restart check")
    diag_table.add_row("[bold]lh --net[/]",   "Full network diagnostics:\ninterfaces, gateway, DNS, ping test,\nDNS resolution, listening ports,\nactive connections, WiFi info, public IP")
    diag_table.add_row("[bold]lh --security[/]",   "Security audit:\nfailed SSH logins, open ports,\nSUID issues, world-writable /etc files,\nnon-root UID 0 users, recent cron/timers,\nknown vulnerabilities (arch-audit)")
    diag_table.add_row("[bold]lh --boot[/]",   "Boot & kernel analysis:\ninstalled kernels, /boot usage,\nGRUB config, systemd-analyze blame,\ndmesg errors, failed services")
    diag_table.add_row("[bold]lh --sensors[/]",   "Hardware sensor readout:\nCPU temps per-core, GPU temp/usage/power,\nfan speeds, disk temps, battery temp,\npower consumption")
    diag_table.add_row("[bold]lh --kernel[/]",   "Deep kernel-level analysis:\nASLR, taint flags, CPU vulnerabilities,\nLSM status, boot params, dmesg errors,\nloaded modules, kernel security settings")
    diag_table.add_row("[bold]lh --malware[/]",   "Malware & rootkit scan:\nhidden process detection,\nSUID binary audit, rootkit file checks,\nsuspicious cron/timer jobs,\nworld-writable PATH, unknown port listeners")
    diag_table.add_row("[bold]lh --restore list[/]", "List available rollback snapshots")
    diag_table.add_row("[bold]lh --restore <id>[/]","Restore a cleanup snapshot")
    diag_table.add_row("[bold]lh --purge-trash[/]", "Permanently delete all rollback snapshots")
    diag_table.add_row("[bold]lh --history[/]",   "Show cleanup history with dates and freed space")
    diag_table.add_row("[bold]lh --version[/]",   "Show version")
    console.print(diag_table)
    console.print()

    clean_table = Table(title="Cleanup Commands", box=box.SIMPLE)
    clean_table.add_column("Command", style="bold yellow", width=20)
    clean_table.add_column("What it does")
    clean_table.add_row("[bold]lh --clean[/]",         "Run all safe cleanups with rollback:\n  • User cache (pip, yay, npm, cargo, etc.)\n  • Thumbnail cache\n  • /tmp\n  • Journal logs (7d)\n  • Pacman cache (paccache -rk2)\n  • Unused Flatpak runtimes\n  • Everything is moved to rollback storage\n  • Restore with: lh --restore <id>")
    clean_table.add_row("[bold]lh --clean --dry-run[/]","Preview what would be deleted\nwithout actually removing anything")
    console.print(clean_table)
    console.print()

    config_table = Table(title="Configuration", box=box.SIMPLE, padding=(0, 2))
    config_table.add_column("Key", style="bold yellow")
    config_table.add_column("Default")
    config_table.add_column("Description")
    config_table.add_row("config file", "~/.config/linux-health/config.toml", "TOML config file")
    config_table.add_row("logs/history", "~/.local/share/linux-health/", "JSON logs & cleanup history")
    config_table.add_row("systemd", "~/.config/systemd/user/", "linux-health.service + .timer")
    config_table.add_row("auto_cleanup", "true", "Enable scheduled cleanup")
    config_table.add_row("cleanup_interval_days", "7", "Days between cleanups")
    config_table.add_row("notifications", "true", "notify-send after cleanup")
    config_table.add_row("cleanup_*", "true/false", "Toggle specific cleanup modules")
    config_table.add_row("warning_disk_percent", "80", "Disk usage warning threshold")
    config_table.add_row("critical_disk_percent", "90", "Disk usage critical threshold")
    config_table.add_row("large_file_threshold", "1GB", "Threshold for large file detection")
    console.print(config_table)
    console.print()

    console.print(Panel(
        "[bold]Quick start:[/] just run [bold]lh[/]\n"
        "[bold]Weekly auto-maintenance:[/] enabled by default via systemd timer\n"
        "[bold]Source:[/] <5 MB    [bold]Total footprint:[/] <50 MB\n"
        "[bold]Dependencies:[/] python-rich, python-psutil, python-typer",
        title="[bold]NOTES[/]", border_style="green",
    ))
    console.print()


def human_readable(size: int) -> str:
    from linux_health.utils import human_size
    return human_size(size)

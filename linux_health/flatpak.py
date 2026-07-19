from pathlib import Path

from linux_health.utils import command_exists, run_cmd, get_dir_size


def get_cache_size() -> int:
    return get_dir_size(Path("/var/lib/flatpak"))


def clean(dry_run: bool = False, rollback: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    if not command_exists("flatpak"):
        result["error"] = "flatpak not found"
        return result

    size_before = get_cache_size()

    if dry_run:
        result["actions"].append("Would remove unused Flatpak runtimes")
    else:
        output = run_cmd(["flatpak", "uninstall", "--unused", "--noninteractive"], timeout=60)
        if output is not None:
            result["actions"].append("Removed unused Flatpak runtimes")

    size_after = get_cache_size()
    result["freed"] = size_before - size_after
    return result

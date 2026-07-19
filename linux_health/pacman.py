from linux_health.utils import command_exists, run_cmd


def get_cache_size() -> int:
    from linux_health.utils import get_dir_size
    from pathlib import Path
    return get_dir_size(Path("/var/cache/pacman/pkg"))


def clean(dry_run: bool = False, rollback: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    if not command_exists("paccache"):
        result["error"] = "paccache not found"
        return result

    size_before = get_cache_size()

    if dry_run:
        output = run_cmd(["paccache", "-rk2", "--dryrun"])
        if output:
            result["actions"].append(f"Would remove old pacman packages")
    else:
        output = run_cmd(["paccache", "-rk2"])
        if output:
            result["actions"].append("Removed old pacman packages")

    size_after = get_cache_size()
    result["freed"] = size_before - size_after
    return result

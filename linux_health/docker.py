from linux_health.utils import command_exists, run_cmd, human_size


def get_docker_size() -> int:
    if not command_exists("docker"):
        return 0
    try:
        output = run_cmd(
            ["docker", "system", "df", "--format", "{{.Size}}"],
            timeout=15,
        )
        if output:
            total = 0
            for line in output.splitlines():
                s = line.strip()
                if s.endswith("GB"):
                    total += float(s.replace("GB", "").strip()) * 1024**3
                elif s.endswith("MB"):
                    total += float(s.replace("MB", "").strip()) * 1024**2
                elif s.endswith("kB"):
                    total += float(s.replace("kB", "").strip()) * 1024
                elif s.endswith("B"):
                    total += float(s.replace("B", "").strip())
            return int(total)
    except Exception:
        pass
    return 0


def get_info() -> dict:
    size = get_docker_size()
    return {
        "size": size,
        "size_h": human_size(size),
        "installed": command_exists("docker"),
    }


def clean(dry_run: bool = False) -> dict:
    result: dict = {"freed": 0, "actions": []}
    if not command_exists("docker"):
        result["error"] = "docker not found"
        return result

    if dry_run:
        result["actions"].append("Would prune Docker system")
        return result

    output = run_cmd(["docker", "system", "prune", "-f"], timeout=60)
    if output is not None:
        result["actions"].append("Pruned Docker system")
    return result

from pathlib import Path

from linux_health.utils import get_dir_size, human_size


def get_dev_info() -> dict:
    info: dict = {}

    maven_dir = Path.home() / ".m2"
    maven_size = get_dir_size(maven_dir)
    info["maven"] = {
        "path": str(maven_dir),
        "size": maven_size,
        "size_h": human_size(maven_size),
        "exists": maven_dir.exists(),
    }

    gradle_dir = Path.home() / ".gradle"
    gradle_size = get_dir_size(gradle_dir)
    info["gradle"] = {
        "path": str(gradle_dir),
        "size": gradle_size,
        "size_h": human_size(gradle_size),
        "exists": gradle_dir.exists(),
    }

    target_dirs = []
    target_total = 0
    for root in [Path.home() / "Projects", Path.home() / "projects",
                  Path.home() / "code", Path.home() / "Code"]:
        if root.exists():
            try:
                for p in root.rglob("target"):
                    if p.is_dir():
                        s = get_dir_size(p)
                        target_dirs.append({"path": str(p), "size": s, "size_h": human_size(s)})
                        target_total += s
            except (PermissionError, OSError):
                pass
    info["target"] = {
        "dirs": target_dirs,
        "total": target_total,
        "total_h": human_size(target_total),
    }

    build_dirs = []
    build_total = 0
    for root in [Path.home() / "Projects", Path.home() / "projects",
                  Path.home() / "code", Path.home() / "Code"]:
        if root.exists():
            try:
                for p in root.rglob("build"):
                    if p.is_dir():
                        s = get_dir_size(p)
                        build_dirs.append({"path": str(p), "size": s, "size_h": human_size(s)})
                        build_total += s
            except (PermissionError, OSError):
                pass
    info["build"] = {
        "dirs": build_dirs,
        "total": build_total,
        "total_h": human_size(build_total),
    }

    node_modules_dirs = []
    node_total = 0
    for root in [Path.home() / "Projects", Path.home() / "projects",
                  Path.home() / "code", Path.home() / "Code"]:
        if root.exists():
            try:
                for p in root.rglob("node_modules"):
                    if p.is_dir():
                        s = get_dir_size(p)
                        node_modules_dirs.append({"path": str(p), "size": s, "size_h": human_size(s)})
                        node_total += s
            except (PermissionError, OSError):
                pass
    info["node_modules"] = {
        "dirs": node_modules_dirs,
        "total": node_total,
        "total_h": human_size(node_total),
    }

    return info

import subprocess
from pathlib import Path

from linux_health.utils import human_size


def get_disk_usage(path: str = "/") -> dict | None:
    try:
        import psutil
        usage = psutil.disk_usage(path)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
            "total_h": human_size(usage.total),
            "used_h": human_size(usage.used),
            "free_h": human_size(usage.free),
            "mount": path,
        }
    except ImportError:
        pass
    try:
        result = subprocess.run(
            ["df", "-B1", path], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    return {
                        "total": total,
                        "used": used,
                        "free": free,
                        "percent": round((used / total) * 100, 1) if total else 0,
                        "total_h": human_size(total),
                        "used_h": human_size(used),
                        "free_h": human_size(free),
                        "mount": path,
                    }
    except Exception:
        pass
    return None


def get_all_mounts() -> list[dict]:
    mounts: list[dict] = []
    try:
        result = subprocess.run(
            ["df", "-B1", "-x", "tmpfs", "-x", "devtmpfs", "-x", "squashfs",
             "-x", "overlay", "-x", "efivarfs", "-x", "proc", "-x", "sysfs",
             "-x", "cgroup", "-x", "cgroup2", "-x", "devpts", "-x", "securityfs",
             "-x", "selinuxfs", "-x", "pstore", "-x", "bpf", "-x", "autofs",
             "-x", "mqueue", "-x", "debugfs", "-x", "tracefs", "-x", "hugetlbfs",
             "-x", "configfs", "-x", "fuse.gvfsd-fuse", "-x", "fuse.portal"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()[1:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 6:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    pct = parts[4].rstrip("%")
                    mount_point = parts[5]
                    try:
                        mounts.append({
                            "mount": mount_point,
                            "total": total,
                            "used": used,
                            "free": free,
                            "percent": float(pct),
                            "total_h": human_size(total),
                            "used_h": human_size(used),
                            "free_h": human_size(free),
                        })
                    except ValueError:
                        pass
    except Exception:
        pass
    return mounts


def get_dir_size_safe(path: Path) -> int:
    try:
        result = subprocess.run(
            ["du", "-sb", str(path)], capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except Exception:
        pass
    return 0


def scan_common_dirs() -> list[dict]:
    home = Path.home()
    targets = [
        ("Downloads", home / "Downloads"),
        ("Documents", home / "Documents"),
        ("Desktop", home / "Desktop"),
        ("Pictures", home / "Pictures"),
        ("Videos", home / "Videos"),
        ("Music", home / "Music"),
        ("Projects", home / "Projects"),
        ("projects", home / "projects"),
        ("Code", home / "Code"),
        ("code", home / "code"),
        (".cache", home / ".cache"),
        (".local", home / ".local"),
        (".config", home / ".config"),
        (".m2", home / ".m2"),
        (".gradle", home / ".gradle"),
        ("snap", home / "snap"),
        (".npm", home / ".npm"),
        (".cargo", home / ".cargo"),
        (".rustup", home / ".rustup"),
        (".gem", home / ".gem"),
        (".pyenv", home / ".pyenv"),
    ]
    results = []
    for name, path in targets:
        size = get_dir_size_safe(path)
        if size > 0:
            results.append({
                "name": name,
                "path": str(path),
                "size": size,
                "size_h": human_size(size),
            })
    results.sort(key=lambda x: x["size"], reverse=True)
    return results


def get_largest_dirs(base: str = "~", count: int = 15, min_size: int = 100 * 1024 * 1024) -> list[dict]:
    home = Path(base).expanduser()
    if not home.exists():
        return []

    results: list[dict] = []
    try:
        result = subprocess.run(
            ["du", "-sb", "--max-depth=1", str(home)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) == 2:
                    size = int(parts[0])
                    name = parts[1]
                    if size >= min_size and name != str(home):
                        results.append({
                            "path": name,
                            "size": size,
                            "size_h": human_size(size),
                        })
    except Exception:
        pass

    results.sort(key=lambda x: x["size"], reverse=True)
    return results[:count]


def get_largest_files(search_dirs: list[str] | None = None, count: int = 15,
                      min_size: int = 100 * 1024 * 1024) -> list[dict]:
    if search_dirs is None:
        search_dirs = [str(Path.home())]

    results: list[dict] = []
    for base in search_dirs:
        path = Path(base).expanduser()
        if not path.exists():
            continue
        try:
            result = subprocess.run(
                ["find", str(path), "-type", "f", "-size", f"+{min_size}c",
                 "-exec", "ls", "-1s", "{}", ";"],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    try:
                        blocks = int(parts[0])
                        filepath = parts[1]
                        size = blocks * 1024
                        if size >= min_size and not filepath.startswith("/proc"):
                            results.append({
                                "path": filepath,
                                "size": size,
                                "size_h": human_size(size),
                            })
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass

    if not results:
        try:
            result = subprocess.run(
                ["find", str(Path.home()), "-type", "f", "-size", f"+{min_size}c"],
                capture_output=True, text=True, timeout=30,
            )
            for filepath in result.stdout.strip().splitlines():
                if not filepath:
                    continue
                try:
                    fpath = Path(filepath)
                    size = fpath.stat().st_size
                    if size >= min_size:
                        results.append({
                            "path": filepath,
                            "size": size,
                            "size_h": human_size(size),
                        })
                except (OSError, ValueError):
                    pass
        except Exception:
            pass

    results.sort(key=lambda x: x["size"], reverse=True)
    return results[:count]


def analyze_disk() -> dict:
    usage = get_disk_usage()
    mounts = get_all_mounts()
    common = scan_common_dirs()
    largest_dirs = get_largest_dirs()
    largest_files = get_largest_files()

    return {
        "usage": usage,
        "mounts": mounts,
        "common_dirs": common,
        "largest_dirs": largest_dirs,
        "largest_files": largest_files,
    }

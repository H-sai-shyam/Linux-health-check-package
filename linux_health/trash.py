import json
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from linux_health.config import DATA_DIR
from linux_health.utils import human_size

TRASH_DIR = DATA_DIR / "trash"
DEFAULT_RETENTION_HOURS = 24
MAX_RETENTION_HOURS = 168


def _trash_id() -> str:
    return datetime.now().strftime("cleanup_%Y%m%d_%H%M%S")


def _manifest_path(trash_id: str) -> Path:
    return TRASH_DIR / trash_id / "manifest.json"


def get_snapshots() -> list[dict]:
    if not TRASH_DIR.exists():
        return []
    snapshots = []
    for entry in sorted(TRASH_DIR.iterdir(), reverse=True):
        manifest = entry / "manifest.json"
        if manifest.exists():
            try:
                with open(manifest) as f:
                    data = json.load(f)
                    snapshots.append(data)
            except (json.JSONDecodeError, OSError):
                pass
    return snapshots


def remove_expired(retention_hours: int = DEFAULT_RETENTION_HOURS) -> int:
    if not TRASH_DIR.exists():
        return 0
    now = time.time()
    removed = 0
    for entry in list(TRASH_DIR.iterdir()):
        manifest = entry / "manifest.json"
        if manifest.exists():
            try:
                with open(manifest) as f:
                    data = json.load(f)
                created = data.get("created", "")
                expires = data.get("expires", "")
                if expires:
                    exp_time = datetime.fromisoformat(expires).timestamp()
                    if now > exp_time:
                        shutil.rmtree(entry, ignore_errors=True)
                        removed += 1
            except (json.JSONDecodeError, OSError, ValueError):
                pass
    return removed


def snapshot_info(snap: dict) -> dict:
    items = snap.get("items", [])
    total_size = sum(item.get("size", 0) for item in items if isinstance(item, dict))
    created = snap.get("created", "Unknown")
    expires = snap.get("expires", "Unknown")
    remaining = ""
    if expires and expires != "Unknown":
        try:
            exp = datetime.fromisoformat(expires)
            rem = exp - datetime.now()
            if rem.total_seconds() > 0:
                h = int(rem.total_seconds() // 3600)
                m = int((rem.total_seconds() % 3600) // 60)
                remaining = f"{h}h {m}m"
            else:
                remaining = "Expired"
        except ValueError:
            remaining = "Unknown"

    return {
        "id": snap.get("id", "unknown"),
        "created": created,
        "expires": expires,
        "remaining": remaining,
        "items_count": len(items),
        "total_size": total_size,
        "total_size_h": human_size(total_size),
        "actions": snap.get("actions", []),
    }


def trash_item(src: str) -> dict:
    src_path = Path(src).expanduser().resolve()
    if not src_path.exists():
        return {"error": f"Path not found: {src}", "size": 0}

    tid = _trash_id()
    dest_dir = TRASH_DIR / tid
    dest_dir.mkdir(parents=True, exist_ok=True)

    rel = str(src_path).lstrip("/").replace("/", "_")
    dest = dest_dir / rel

    try:
        size = _get_size(src_path)
        shutil.move(str(src_path), str(dest))
        return {
            "original": str(src_path),
            "trashed": str(dest),
            "size": size,
            "trash_id": tid,
        }
    except shutil.Error as e:
        return {"error": str(e), "size": 0}


def _get_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        import subprocess
        result = subprocess.run(
            ["du", "-sb", str(path)], capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except Exception:
        pass
    return 0


def create_manifest(trash_id: str, items: list[dict], actions: list[str],
                    retention_hours: int = DEFAULT_RETENTION_HOURS) -> dict:
    created = datetime.now()
    expires = created + timedelta(hours=min(retention_hours, MAX_RETENTION_HOURS))
    total_size = sum(item.get("size", 0) for item in items)

    manifest = {
        "id": trash_id,
        "created": created.isoformat(),
        "expires": expires.isoformat(),
        "retention_hours": min(retention_hours, MAX_RETENTION_HOURS),
        "freed": total_size,
        "freed_h": human_size(total_size),
        "items": items,
        "actions": actions,
    }

    manifest_path = _manifest_path(trash_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def restore_snapshot(trash_id: str) -> dict:
    manifest = _manifest_path(trash_id)
    if not manifest.exists():
        return {"error": f"Snapshot not found: {trash_id}"}

    try:
        with open(manifest) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Failed to read manifest: {e}"}

    restored = 0
    errors: list[str] = []
    for item in data.get("items", []):
        original = item.get("original", "")
        trashed = item.get("trashed", "")
        if not trashed or not Path(trashed).exists():
            errors.append(f"Trashed file not found: {original}")
            continue
        try:
            dest = Path(original)
            if dest.exists():
                dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(trashed, str(dest))
            restored += 1
        except (OSError, shutil.Error) as e:
            errors.append(f"Failed to restore {original}: {e}")

    return {
        "id": trash_id,
        "restored": restored,
        "total": len(data.get("items", [])),
        "errors": errors,
    }


def purge_trash() -> dict:
    if not TRASH_DIR.exists():
        return {"purged": 0, "freed": 0}
    total_size = 0
    count = 0
    for entry in list(TRASH_DIR.iterdir()):
        try:
            size = _get_size(entry)
            shutil.rmtree(entry, ignore_errors=True)
            total_size += size
            count += 1
        except OSError:
            pass
    return {"purged": count, "freed": total_size, "freed_h": human_size(total_size)}

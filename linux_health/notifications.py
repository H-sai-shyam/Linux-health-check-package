import subprocess
from linux_health.utils import human_size


def send_cleanup_notification(freed: int) -> bool:
    try:
        subprocess.run(
            [
                "notify-send",
                "--app-name=Linux Health",
                "--urgency=normal",
                "Linux Health",
                f"Weekly maintenance completed.\nFreed: {human_size(freed)}\nRun linux-health for details.",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    except Exception:
        return False

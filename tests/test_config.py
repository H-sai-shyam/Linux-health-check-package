import tempfile
from pathlib import Path

from linux_health.config import load_config, DEFAULT_CONFIG


def test_default_config():
    config = load_config()
    assert config["auto_cleanup"] is True
    assert config["cleanup_interval_days"] == 7
    assert config["warning_disk_percent"] == 80
    assert config["critical_disk_percent"] == 90
    assert config["max_logs"] == 50

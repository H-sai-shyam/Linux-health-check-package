import pytest
from linux_health.utils import human_size, parse_size


def test_human_size():
    assert human_size(0) == "0B"
    assert human_size(1024) == "1.0KB"
    assert human_size(1024 * 1024) == "1.0MB"
    assert human_size(1024 * 1024 * 1024) == "1.0GB"


def test_parse_size():
    assert parse_size("1KB") == 1024
    assert parse_size("1MB") == 1024 * 1024
    assert parse_size("1GB") == 1024 * 1024 * 1024
    assert parse_size("1024") == 1024

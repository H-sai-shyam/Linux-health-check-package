# Linux Health

A lightweight native Linux system health monitoring and maintenance utility.

## Installation

```bash
git clone <repo-url>
cd linux-health
chmod +x install.sh
./install.sh
```

## Usage

```bash
# Show complete dashboard
linux-health

# Only scan (no cleanup)
linux-health --scan

# Run cleanup immediately
linux-health --clean

# Show what would be deleted
linux-health --clean --dry-run

# Detailed disk analysis
linux-health --disk

# Show cleanup history
linux-health --history

# Run diagnostics
linux-health --doctor

# Show version
linux-health --version
```

## Requirements

- Python 3.10+
- systemd (for automatic scheduling)

### Dependencies (installed via pip)

- rich
- psutil
- typer

## Automatic Maintenance

The tool installs a systemd timer that runs weekly maintenance automatically.
If the system is off on the scheduled day, it runs on the next boot.

## Configuration

`~/.config/linux-health/config.toml`

## Project

- Source: <5 MB
- Config: <100 KB
- Logs: max 5 MB
- Total: <50 MB

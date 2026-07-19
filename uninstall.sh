#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/.config/linux-health"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
DATA_DIR="${HOME}/.local/share/linux-health"

echo "Uninstalling Linux Health..."

# Stop and disable systemd timer
systemctl --user stop linux-health.timer 2>/dev/null || true
systemctl --user disable linux-health.timer 2>/dev/null || true

# Remove symlink
rm -f "${HOME}/.local/bin/lh"

# Remove systemd files
rm -f "${SYSTEMD_DIR}/linux-health.service"
rm -f "${SYSTEMD_DIR}/linux-health.timer"
systemctl --user daemon-reload 2>/dev/null || true

# Uninstall Python package
pip uninstall -y linux-health 2>/dev/null || \
    python3 -m pip uninstall -y linux-health 2>/dev/null || true

# Remove config
rm -rf "${CONFIG_DIR}"

# Ask about logs
if [ -d "${DATA_DIR}" ]; then
    echo ""
    echo "Logs and history are stored at: ${DATA_DIR}"
    read -r -p "Remove logs and history? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf "${DATA_DIR}"
        echo "Logs removed."
    else
        echo "Logs preserved at ${DATA_DIR}"
    fi
fi

echo ""
echo "Linux Health has been uninstalled."

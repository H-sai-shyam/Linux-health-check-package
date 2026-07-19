#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/.config/linux-health"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing Linux Health..."

# Install Python package (system Python, user install)
python3 -m pip install --user "${PROJECT_DIR}" 2>/dev/null || \
    python3 -m pip install --user --break-system-packages "${PROJECT_DIR}"

# Ensure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":${HOME}/.local/bin:"* ]]; then
    echo "NOTE: Add ${HOME}/.local/bin to your PATH, then run:"
    echo "  export PATH=\"${HOME}/.local/bin:\$PATH\""
    export PATH="${HOME}/.local/bin:${PATH}"
fi

# Create config directory
mkdir -p "${CONFIG_DIR}" "${SYSTEMD_DIR}"

# Install default config if not exists
if [ ! -f "${CONFIG_DIR}/config.toml" ]; then
    cat > "${CONFIG_DIR}/config.toml" << 'EOF'
auto_cleanup = true
cleanup_interval_days = 7
notifications = true
cleanup_cache = true
cleanup_pacman = true
cleanup_flatpak = true
cleanup_tmp = true
cleanup_journal = true
cleanup_maven = false
cleanup_gradle = false
cleanup_docker = false
cleanup_build = false
cleanup_target = false
warning_disk_percent = 80
critical_disk_percent = 90
large_file_threshold = "1GB"
max_logs = 50
EOF
    echo "Created default config at ${CONFIG_DIR}/config.toml"
fi

# Install systemd files
cp "${PROJECT_DIR}/systemd/linux-health.service" "${SYSTEMD_DIR}/"
cp "${PROJECT_DIR}/systemd/linux-health.timer" "${SYSTEMD_DIR}/"

# Create shortcut symlink
ln -sf "${BIN_DIR}/linux-health" "${BIN_DIR}/lh"

# Reload and enable timer
systemctl --user daemon-reload 2>/dev/null || true
systemctl --user enable linux-health.timer 2>/dev/null || true
systemctl --user start linux-health.timer 2>/dev/null || true

echo ""
echo "Linux Health installed successfully!"
echo ""
echo "Run 'linux-health' or 'lh' to see your system dashboard."
echo "Run 'lh --doctor' for diagnostics."
echo "Run 'lh --clean' for immediate cleanup."
echo ""
echo "Automatic weekly maintenance has been scheduled."

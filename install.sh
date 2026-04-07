#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# install.sh — One-step installer for Raspberry Pi 4B
#
# This script sets up EVERYTHING needed to run the Garbage Collector
# Robot on a fresh Raspberry Pi 4B:
#   1. System dependencies (libatlas, v4l-utils, etc.)
#   2. Python virtual environment
#   3. PyTorch ARM64 wheel
#   4. Pip requirements
#   5. WiFi Hotspot (192.168.4.1)
#   6. Auto-start systemd service
#   7. Create required directories
#
# Usage: sudo ./install.sh
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="${SUDO_USER:-pi}"
VENV_DIR="$SCRIPT_DIR/venv"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   🤖 Autonomous Garbage Collector — Installer   ║"
echo "║   Platform: Raspberry Pi 4B                      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo: sudo ./install.sh"
    exit 1
fi

# ─── Step 1: System Dependencies ───
echo "━━━ Step 1/7: Installing system dependencies ━━━"
apt update
apt install -y \
    python3-pip python3-venv python3-dev \
    libatlas-base-dev libopenjp2-7 libtiff5 \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev v4l-utils \
    git hostapd dnsmasq \
    libjpeg-dev zlib1g-dev libffi-dev

echo "✓ System dependencies installed"

# ─── Step 2: Python Virtual Environment ───
echo ""
echo "━━━ Step 2/7: Setting up Python virtual environment ━━━"
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists, updating..."
else
    sudo -u "$USER_NAME" python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install -U pip setuptools wheel
echo "✓ Virtual environment ready"

# ─── Step 3: Install PyTorch (ARM64 CPU wheel) ───
echo ""
echo "━━━ Step 3/7: Installing PyTorch for ARM64 ━━━"
echo "This may take several minutes..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
echo "✓ PyTorch installed"

# ─── Step 4: Install Python Requirements ───
echo ""
echo "━━━ Step 4/7: Installing Python packages ━━━"
pip install -r "$SCRIPT_DIR/requirements.txt"
echo "✓ Python packages installed"

# ─── Step 5: Create Directories ───
echo ""
echo "━━━ Step 5/7: Creating required directories ━━━"
sudo -u "$USER_NAME" mkdir -p "$SCRIPT_DIR/models"
sudo -u "$USER_NAME" mkdir -p "$SCRIPT_DIR/data/driving/left"
sudo -u "$USER_NAME" mkdir -p "$SCRIPT_DIR/data/driving/forward"
sudo -u "$USER_NAME" mkdir -p "$SCRIPT_DIR/data/driving/right"
sudo -u "$USER_NAME" mkdir -p "$SCRIPT_DIR/data/driving/stop"
echo "✓ Directories created"

# ─── Step 6: WiFi Hotspot ───
echo ""
echo "━━━ Step 6/7: Setting up WiFi Hotspot ━━━"

# Read SSID/password from user_settings.json if it exists
SSID="GarbageBot"
PASSWORD="robot1234"
if [ -f "$SCRIPT_DIR/user_settings.json" ]; then
    SSID=$(python3 -c "import json; d=json.load(open('$SCRIPT_DIR/user_settings.json')); print(d.get('hotspot_ssid', 'GarbageBot'))" 2>/dev/null || echo "GarbageBot")
    PASSWORD=$(python3 -c "import json; d=json.load(open('$SCRIPT_DIR/user_settings.json')); print(d.get('hotspot_password', 'robot1234'))" 2>/dev/null || echo "robot1234")
fi

bash "$SCRIPT_DIR/setup_hotspot.sh" "$SSID" "$PASSWORD"
echo "✓ WiFi Hotspot configured"

# ─── Step 7: Systemd Auto-start Service ───
echo ""
echo "━━━ Step 7/7: Creating auto-start service ━━━"

cat > /etc/systemd/system/garbagebot.service << EOF
[Unit]
Description=Autonomous Garbage Collector Robot
After=network.target hostapd.service
Wants=hostapd.service dnsmasq.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Give the Pi time to settle before starting
ExecStartPre=/bin/sleep 5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable garbagebot.service
echo "✓ Auto-start service created"

# ─── Step 8: Serial Port Permissions ───
echo ""
echo "━━━ Bonus: Setting serial port permissions ━━━"
usermod -aG dialout "$USER_NAME" 2>/dev/null || true
usermod -aG video "$USER_NAME" 2>/dev/null || true
echo "✓ User '$USER_NAME' added to dialout and video groups"

# ─── Done! ───
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              ✅ Installation Complete!            ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║  WiFi Network:  $SSID"
echo "║  WiFi Password: $PASSWORD"
echo "║  Dashboard URL: http://192.168.4.1:5000          ║"
echo "║                                                  ║"
echo "║  To start now:                                   ║"
echo "║    sudo systemctl start garbagebot               ║"
echo "║                                                  ║"
echo "║  Or just reboot — it starts automatically!       ║"
echo "║    sudo reboot                                   ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# install.sh — One-step installer for Raspberry Pi 4B ONLY
#
# This script sets up EVERYTHING needed to run the Garbage Collector
# Robot on a FRESH Raspberry Pi 4B (Raspberry Pi OS 64-bit):
#   1. Hardware validation (Pi 4B + ARM64 enforced)
#   2. System dependencies
#   3. Python virtual environment
#   4. PyTorch ARM64 wheel (Pi 4B-tested build)
#   5. Pip requirements
#   6. GPIO / Serial / Camera configuration
#   7. WiFi Hotspot (192.168.4.1)
#   8. Auto-start systemd service
#   9. Required directories
#
# Usage: sudo ./install.sh
# ═══════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="${SUDO_USER:-pi}"
VENV_DIR="$SCRIPT_DIR/venv"

# ─── Colour helpers ───
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
die()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   🤖 Autonomous Garbage Collector — Installer   ║"
echo "║   Target: Raspberry Pi 4B (ARM64)                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── Root check ───
[ "$EUID" -ne 0 ] && die "Please run with sudo: sudo ./install.sh"

# ═══════════════════════════════════════════════════════════════════
# STEP 0 — Hardware Validation (Pi 4B + ARM64 only)
# ═══════════════════════════════════════════════════════════════════
echo "━━━ Step 0/9: Validating hardware ━━━"

# Enforce 64-bit ARM (aarch64)
ARCH=$(uname -m)
[ "$ARCH" != "aarch64" ] && \
    die "Wrong architecture: $ARCH. This installer requires a 64-bit (aarch64) Raspberry Pi OS."

# Enforce Pi 4B specifically via /proc/cpuinfo
PI_MODEL=$(grep -i "model name\|Model" /proc/cpuinfo | grep -i "Raspberry Pi 4" | head -1 || true)
if [ -z "$PI_MODEL" ]; then
    # Fallback: check /proc/device-tree/model
    DT_MODEL=$(cat /proc/device-tree/model 2>/dev/null || true)
    echo "$DT_MODEL" | grep -qi "Raspberry Pi 4" || \
        die "This installer is for Raspberry Pi 4B only. Detected: ${DT_MODEL:-unknown board}."
fi

ok "Hardware validated: Raspberry Pi 4B (aarch64)"

# ═══════════════════════════════════════════════════════════════════
# STEP 1 — System Dependencies
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 1/9: Installing system dependencies ━━━"

OS_VERSION=$(grep -oP '(?<=VERSION_CODENAME=)\w+' /etc/os-release 2>/dev/null || echo "bullseye")
echo "Detected OS: Raspberry Pi OS $OS_VERSION"

apt-get update -qq

# ── Core packages (all Pi OS versions) ──────────────────────────
apt-get install -y \
    python3-pip python3-venv python3-dev \
    libopenblas-dev \
    libopenjp2-7 libjpeg-dev zlib1g-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev v4l-utils \
    libffi-dev libssl-dev \
    libi2c-dev i2c-tools \
    python3-libgpiod \
    git \
    raspi-config \
    curl

# hostapd+dnsmasq only needed on Bullseye (dhcpcd systems)
# On NM systems (Bookworm/Trixie+), NetworkManager handles AP mode natively
if ! command -v nmcli &>/dev/null; then
    apt-get install -y hostapd dnsmasq
fi

# ── Post-Bullseye vs Bullseye package variants ──────────────────
# Detect based on tools, not codename (handles Trixie, Bookworm, future)
if command -v nmcli &>/dev/null; then
    # Bookworm / Trixie / future — uses NetworkManager, new package names
    apt-get install -y \
        libgpiod2t64 \
        raspi-utils-core raspi-utils-dt 2>/dev/null || \
        warn "Some raspi-utils packages unavailable — raspi-config will still work"
else
    # Bullseye and older — uses dhcpcd, legacy package names
    apt-get install -y \
        libatlas-base-dev \
        libgpiod2 \
        libraspberrypi-bin 2>/dev/null || \
        warn "Some packages unavailable on this OS version — continuing"
fi

ok "System dependencies installed ($OS_VERSION)"

# ═══════════════════════════════════════════════════════════════════
# STEP 2 — Pi 4B Hardware Interfaces
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 2/9: Configuring Pi 4B hardware interfaces ━━━"

# Enable UART (for dual-Arduino serial comms)
if command -v raspi-config &>/dev/null; then
    raspi-config nonint do_serial_hw 0      # Enable serial hardware
    raspi-config nonint do_serial_cons 1    # Disable login shell over serial
    ok "UART / Serial enabled (for Arduino communication)"

    # Enable I2C
    raspi-config nonint do_i2c 0
    ok "I2C enabled"

    # Enable Camera (legacy + libcamera)
    raspi-config nonint do_camera 0 2>/dev/null || \
        warn "Camera toggle skipped (may already be enabled or using libcamera)"
else
    warn "raspi-config not found — manually enable Serial, I2C, Camera via sudo raspi-config"
fi

# Disable serial console to free UART0 for Arduinos
# Bookworm moved cmdline.txt to /boot/firmware/
if [ -f /boot/firmware/cmdline.txt ]; then
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
else
    CMDLINE_FILE="/boot/cmdline.txt"
fi
if grep -q "console=serial0" "$CMDLINE_FILE" 2>/dev/null; then
    sed -i 's/console=serial0,[0-9]* //' "$CMDLINE_FILE"
    ok "Serial console removed from $CMDLINE_FILE"
fi

# Enable /dev/gpiomem access
usermod -aG dialout "$USER_NAME" 2>/dev/null || true
usermod -aG video   "$USER_NAME" 2>/dev/null || true
usermod -aG gpio    "$USER_NAME" 2>/dev/null || true
usermod -aG i2c     "$USER_NAME" 2>/dev/null || true
ok "User '$USER_NAME' added to dialout, video, gpio, i2c groups"

# ═══════════════════════════════════════════════════════════════════
# STEP 3 — Python Virtual Environment
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 3/9: Setting up Python virtual environment ━━━"

if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists — updating..."
else
    sudo -u "$USER_NAME" python3 -m venv --system-site-packages "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Pin setuptools <82 — torch requires setuptools<82, versions >=82 break the install
pip install -U pip wheel --quiet
pip install "setuptools<82" --quiet
ok "Virtual environment ready at $VENV_DIR"

# ═══════════════════════════════════════════════════════════════════
# STEP 4 — PyTorch (Pi 4B ARM64-tested wheel)
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 4/9: Installing PyTorch for Raspberry Pi 4B (ARM64) ━━━"
echo "    This may take 5-10 minutes on first install..."

# torch==2.1.0 does not exist for aarch64 on PyTorch's CPU index.
# Earliest available aarch64 CPU wheel is 2.6.0.
# Install latest stable from the index — resolves automatically.
pip install \
    torch \
    torchvision \
    --index-url https://download.pytorch.org/whl/cpu \
    --prefer-binary \
    --quiet

# Capture installed version for the summary banner
TORCH_VERSION=$(python3 -c "import torch; print(torch.__version__)" 2>/dev/null || echo "unknown")
ok "PyTorch $TORCH_VERSION installed (CPU, aarch64)"

# ═══════════════════════════════════════════════════════════════════
# STEP 5 — Python Requirements
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 5/9: Installing Python packages ━━━"

if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    warn "requirements.txt not found — skipping"
else
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
    ok "Python packages installed"
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 6 — Required Directories
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 6/9: Creating required directories ━━━"

sudo -u "$USER_NAME" mkdir -p \
    "$SCRIPT_DIR/models" \
    "$SCRIPT_DIR/data/driving/left" \
    "$SCRIPT_DIR/data/driving/forward" \
    "$SCRIPT_DIR/data/driving/right" \
    "$SCRIPT_DIR/data/driving/stop" \
    "$SCRIPT_DIR/logs"

ok "Directories created"

# ═══════════════════════════════════════════════════════════════════
# STEP 7 — WiFi Hotspot
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 7/9: Setting up WiFi Hotspot ━━━"

SSID="GarbageBot"
PASSWORD="robot1234"
if [ -f "$SCRIPT_DIR/user_settings.json" ]; then
    SSID=$(python3 -c \
        "import json; d=json.load(open('$SCRIPT_DIR/user_settings.json')); print(d.get('hotspot_ssid','GarbageBot'))" \
        2>/dev/null || echo "GarbageBot")
    PASSWORD=$(python3 -c \
        "import json; d=json.load(open('$SCRIPT_DIR/user_settings.json')); print(d.get('hotspot_password','robot1234'))" \
        2>/dev/null || echo "robot1234")
fi

if [ -f "$SCRIPT_DIR/setup_hotspot.sh" ]; then
    bash "$SCRIPT_DIR/setup_hotspot.sh" "$SSID" "$PASSWORD"
    ok "WiFi Hotspot configured (SSID: $SSID)"
else
    warn "setup_hotspot.sh not found — skipping hotspot configuration"
fi

# ═══════════════════════════════════════════════════════════════════
# STEP 8 — Systemd Auto-start Service
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 8/9: Creating auto-start systemd service ━━━"

cat > /etc/systemd/system/garbagebot.service << EOF
[Unit]
Description=Autonomous Garbage Collector Robot (Pi 4B)
After=network.target hostapd.service
Wants=hostapd.service dnsmasq.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SCRIPT_DIR
ExecStartPre=/bin/sleep 5
ExecStart=$VENV_DIR/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
# Ensure ARM CPU governor is set for consistent performance
ExecStartPre=/bin/bash -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor || true'

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable garbagebot.service
ok "Auto-start service enabled"

# ═══════════════════════════════════════════════════════════════════
# STEP 9 — GPU Memory Split (Pi 4B optimisation)
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 9/9: Optimising Pi 4B GPU memory split ━━━"

# Bookworm moved config.txt to /boot/firmware/
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
else
    CONFIG_FILE="/boot/config.txt"
fi
# Allocate minimum GPU RAM (16 MB) — frees more RAM for PyTorch inference
if ! grep -q "^gpu_mem=" "$CONFIG_FILE" 2>/dev/null; then
    echo "gpu_mem=16" >> "$CONFIG_FILE"
    ok "GPU memory set to 16 MB (maximises RAM for PyTorch)"
else
    sed -i 's/^gpu_mem=.*/gpu_mem=16/' "$CONFIG_FILE"
    ok "GPU memory updated to 16 MB"
fi

# ─── Done! ───
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         ✅ Installation Complete!                 ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
printf "║  WiFi Network:  %-35s║\n" "$SSID"
printf "║  WiFi Password: %-35s║\n" "$PASSWORD"
echo "║  Dashboard URL: http://192.168.4.1:5000          ║"
echo "║                                                  ║"
printf "║  PyTorch:       %-35s║\n" "$TORCH_VERSION (CPU, aarch64)"
echo "║  Serial UART:   Enabled (for Arduinos)           ║"
echo "║  GPU RAM:       16 MB (max RAM for inference)    ║"
echo "║                                                  ║"
echo "║  ⚠  A reboot is required for all changes        ║"
echo "║     to take effect (serial, GPIO, camera)        ║"
echo "║                                                  ║"
echo "║  After reboot — robot starts automatically.      ║"
echo "║    sudo reboot                                   ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
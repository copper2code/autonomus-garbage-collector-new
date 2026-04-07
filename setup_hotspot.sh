#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# setup_hotspot.sh — Configure Raspberry Pi 4B as a WiFi Access Point
#
# Compatible with:
#   - Raspberry Pi OS Bullseye (uses dhcpcd)
#   - Raspberry Pi OS Bookworm / Trixie+ (uses NetworkManager)
#
# Detection is based on which tools are installed, not OS codename,
# so this script is forward-compatible with future releases.
#
# Creates a WiFi hotspot so you can connect directly to the robot
# and access the dashboard at http://192.168.4.1:5000
#
# Usage:  sudo ./setup_hotspot.sh [SSID] [PASSWORD] [COUNTRY_CODE]
# Default: SSID=GarbageBot  PASSWORD=robot1234  COUNTRY=IN
# ═══════════════════════════════════════════════════════════════════

set -e

SSID="${1:-GarbageBot}"
PASSWORD="${2:-robot1234}"
COUNTRY="${3:-IN}"          # Pass your 2-letter ISO country code
AP_IP="192.168.4.1"
DHCP_RANGE_START="192.168.4.10"
DHCP_RANGE_END="192.168.4.50"
WLAN_IFACE="wlan0"

# ─── Colour helpers ───
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
die()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "══════════════════════════════════════════"
echo "  🤖 Garbage Collector — WiFi Hotspot Setup"
echo "══════════════════════════════════════════"
echo "  SSID:        $SSID"
echo "  Password:    $PASSWORD"
echo "  IP:          $AP_IP"
echo "  Interface:   $WLAN_IFACE"
echo "  Country:     $COUNTRY"
echo "══════════════════════════════════════════"
echo ""

# ─── Root check ───
[ "$EUID" -ne 0 ] && die "Please run with sudo: sudo ./setup_hotspot.sh"

# ═══════════════════════════════════════════════════════════════════
# Input Validation
# ═══════════════════════════════════════════════════════════════════

# WPA2 requires password between 8 and 63 characters
PW_LEN=${#PASSWORD}
if [ "$PW_LEN" -lt 8 ] || [ "$PW_LEN" -gt 63 ]; then
    die "WiFi password must be 8–63 characters (current: $PW_LEN). WPA2 requirement."
fi

# SSID must be 1–32 characters
SSID_LEN=${#SSID}
if [ "$SSID_LEN" -lt 1 ] || [ "$SSID_LEN" -gt 32 ]; then
    die "SSID must be 1–32 characters (current: $SSID_LEN)."
fi

# Country code must be exactly 2 uppercase letters
if ! echo "$COUNTRY" | grep -qE '^[A-Z]{2}$'; then
    die "Country code must be 2 uppercase letters (e.g. IN, US, GB). Got: '$COUNTRY'"
fi

ok "Inputs validated"

# ═══════════════════════════════════════════════════════════════════
# Detect network manager (tool-based, not codename-based)
# ═══════════════════════════════════════════════════════════════════
OS_VERSION=$(grep -oP '(?<=VERSION_CODENAME=)\w+' /etc/os-release 2>/dev/null || echo "unknown")
echo ""
echo "Detected OS: Raspberry Pi OS $OS_VERSION"

USE_NM=false
if command -v nmcli &>/dev/null; then
    USE_NM=true
    ok "NetworkManager detected (nmcli available) — using NM method"
elif command -v dhcpcd &>/dev/null; then
    ok "dhcpcd detected — using dhcpcd method"
else
    die "Neither NetworkManager (nmcli) nor dhcpcd found. Cannot configure static IP."
fi

# ═══════════════════════════════════════════════════════════════════
# Step 1 — Install required packages
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 1/5: Installing hostapd and dnsmasq ━━━"

apt-get update -qq
apt-get install -y hostapd dnsmasq

# Stop services during config
systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq  2>/dev/null || true

ok "Packages installed"

# ═══════════════════════════════════════════════════════════════════
# Step 2 — Static IP assignment (method depends on OS)
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 2/5: Configuring static IP for $WLAN_IFACE ━━━"

if $USE_NM; then
    # ── Bookworm: NetworkManager ──────────────────────────────────
    # Remove any old GarbageBot NM connection
    nmcli connection delete "GarbageBot-AP" 2>/dev/null || true

    # Create an unmanaged static IP connection for wlan0
    # (hostapd manages the actual AP; NM just sets the IP)
    nmcli connection add \
        type ethernet \
        ifname "$WLAN_IFACE" \
        con-name "GarbageBot-AP" \
        ipv4.method manual \
        ipv4.addresses "$AP_IP/24" \
        ipv4.gateway "" \
        connection.autoconnect yes 2>/dev/null || true

    # Tell NM not to fight hostapd for wlan0
    mkdir -p /etc/NetworkManager/conf.d
    cat > /etc/NetworkManager/conf.d/99-garbagebot-unmanaged.conf << EOF
[keyfile]
unmanaged-devices=interface-name:$WLAN_IFACE
EOF
    systemctl reload NetworkManager 2>/dev/null || true

    # Set IP directly for this session (survives until reboot; NM handles after)
    ip addr flush dev "$WLAN_IFACE" 2>/dev/null || true
    ip addr add "$AP_IP/24" dev "$WLAN_IFACE" 2>/dev/null || true
    ip link set "$WLAN_IFACE" up

else
    # ── Bullseye / dhcpcd systems ─────────────────────────────────

    # Remove any previous block we added
    sed -i '/# GarbageBot Hotspot Config/,/# End GarbageBot/d' /etc/dhcpcd.conf

    cat >> /etc/dhcpcd.conf << EOF
# GarbageBot Hotspot Config
interface $WLAN_IFACE
    static ip_address=$AP_IP/24
    nohook wpa_supplicant
# End GarbageBot
EOF
    systemctl restart dhcpcd
fi

ok "Static IP $AP_IP assigned to $WLAN_IFACE"

# ═══════════════════════════════════════════════════════════════════
# Step 3 — Configure dnsmasq (DHCP server)
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 3/5: Configuring DHCP server (dnsmasq) ━━━"

# Backup original only once
[ -f /etc/dnsmasq.conf ] && [ ! -f /etc/dnsmasq.conf.orig ] && \
    cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig

cat > /etc/dnsmasq.conf << EOF
# GarbageBot DHCP Configuration
interface=$WLAN_IFACE
bind-interfaces
dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,255.255.255.0,24h
domain=local
address=/garbagebot.local/$AP_IP
EOF

ok "dnsmasq configured"

# ═══════════════════════════════════════════════════════════════════
# Step 4 — Configure hostapd (Access Point)
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 4/5: Configuring WiFi Access Point (hostapd) ━━━"

cat > /etc/hostapd/hostapd.conf << EOF
# GarbageBot WiFi Access Point — Pi 4B (brcmfmac driver)
interface=$WLAN_IFACE
driver=nl80211
ssid=$SSID
country_code=$COUNTRY

# 802.11n on 2.4 GHz — best compatibility for Pi 4B brcmfmac
hw_mode=g
ieee80211n=1
channel=6

# Security — WPA2-PSK with CCMP only (TKIP is deprecated and blocked on modern devices)
auth_algs=1
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP

macaddr_acl=0
ignore_broadcast_ssid=0
wmm_enabled=1
EOF

# Point hostapd at its config file
if [ -f /etc/default/hostapd ]; then
    sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
fi

ok "hostapd configured (802.11n, channel 6, WPA2-CCMP, country=$COUNTRY)"

# ═══════════════════════════════════════════════════════════════════
# Step 5 — Enable and start services, then verify
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Step 5/5: Enabling and verifying services ━━━"

systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq

systemctl restart dnsmasq
systemctl restart hostapd

# Give services 3 seconds to settle, then check they're actually running
sleep 3

DNSMASQ_OK=false
HOSTAPD_OK=false

systemctl is-active --quiet dnsmasq  && DNSMASQ_OK=true
systemctl is-active --quiet hostapd  && HOSTAPD_OK=true

if $DNSMASQ_OK; then
    ok "dnsmasq is running"
else
    warn "dnsmasq failed to start — check: sudo journalctl -u dnsmasq -n 30"
fi

if $HOSTAPD_OK; then
    ok "hostapd is running"
else
    warn "hostapd failed to start — check: sudo journalctl -u hostapd -n 30"
    warn "Common cause: country_code '$COUNTRY' may not match your regulatory domain."
    warn "Try: sudo iw reg set $COUNTRY && sudo systemctl restart hostapd"
fi

# ─── Done ───
echo ""
echo "══════════════════════════════════════════"
echo "  ✅ WiFi Hotspot configured!"
echo ""
printf "  Network:   %s\n" "$SSID"
printf "  Password:  %s\n" "$PASSWORD"
printf "  Country:   %s\n" "$COUNTRY"
echo "  Dashboard: http://$AP_IP:5000"
echo "  mDNS:      http://garbagebot.local:5000"
echo ""
echo "  Connect your phone/laptop to '$SSID'"
echo "  Then open http://$AP_IP:5000"
echo ""
if ! $HOSTAPD_OK || ! $DNSMASQ_OK; then
    echo "  ⚠  One or more services failed. See warnings above."
fi
echo "══════════════════════════════════════════"
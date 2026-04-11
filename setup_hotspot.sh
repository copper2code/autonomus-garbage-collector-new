#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# setup_hotspot.sh — Configure Raspberry Pi 4B as a WiFi Access Point
#
# Compatible with:
#   - Raspberry Pi OS Bullseye (uses hostapd + dnsmasq)
#   - Raspberry Pi OS Bookworm / Trixie+ (uses NetworkManager native AP)
#
# Detection is based on which tools are installed, not OS codename,
# so this script is forward-compatible with future releases.
#
# Creates a WiFi hotspot so you can connect directly to the robot
# and access the dashboard at http://192.168.4.1:5000
#
# Usage:  sudo ./setup_hotspot.sh [SSID] [COUNTRY_CODE]
# Default: SSID=GarbageBot  COUNTRY=IN
# ═══════════════════════════════════════════════════════════════════

set -e

SSID="${1:-GarbageBot}"
PASSWORD="${2:-robot1234}"
COUNTRY="${3:-IN}"
AP_IP="192.168.4.1"
DHCP_RANGE_START="192.168.4.10"
DHCP_RANGE_END="192.168.4.50"
WLAN_IFACE="wlan0"
NM_CON_NAME="GarbageBot-AP"

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

PW_LEN=${#PASSWORD}
if [ "$PW_LEN" -lt 8 ] || [ "$PW_LEN" -gt 63 ]; then
    die "WiFi password must be 8–63 characters (current: $PW_LEN). WPA2 requirement."
fi
SSID_LEN=${#SSID}
if [ "$SSID_LEN" -lt 1 ] || [ "$SSID_LEN" -gt 32 ]; then
    die "SSID must be 1–32 characters (current: $SSID_LEN)."
fi

if ! echo "$COUNTRY" | grep -qE '^[A-Z]{2}$'; then
    die "Country code must be 2 uppercase letters (e.g. IN, US, GB). Got: '$COUNTRY'"
fi

ok "Inputs validated"

# ═══════════════════════════════════════════════════════════════════
# Detect network management method
# ═══════════════════════════════════════════════════════════════════
OS_VERSION=$(grep -oP '(?<=VERSION_CODENAME=)\w+' /etc/os-release 2>/dev/null || echo "unknown")
echo ""
echo "Detected OS: Raspberry Pi OS $OS_VERSION"

USE_NM=false
if command -v nmcli &>/dev/null; then
    USE_NM=true
    ok "NetworkManager detected — using native NM Access Point mode"
elif command -v dhcpcd &>/dev/null; then
    ok "dhcpcd detected — using hostapd + dnsmasq method"
else
    die "Neither NetworkManager (nmcli) nor dhcpcd found. Cannot configure hotspot."
fi

# ═══════════════════════════════════════════════════════════════════
# Set WiFi regulatory domain
# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━ Setting WiFi country code to $COUNTRY ━━━"
iw reg set "$COUNTRY" 2>/dev/null || warn "Could not set regulatory domain via iw"

# Also persist in wpa_supplicant for Bullseye
if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
    if ! grep -q "country=" /etc/wpa_supplicant/wpa_supplicant.conf; then
        sed -i "1i country=$COUNTRY" /etc/wpa_supplicant/wpa_supplicant.conf
    fi
fi
ok "WiFi regulatory domain: $COUNTRY"

# Ensure WiFi is not blocked
rfkill unblock wifi 2>/dev/null || true

if $USE_NM; then
    # ═══════════════════════════════════════════════════════════════
    # NetworkManager method (Bookworm / Trixie / future)
    #
    # Uses NM's built-in AP mode — handles hostapd + DHCP internally.
    # Much more reliable than manually configuring hostapd on NM systems.
    # ═══════════════════════════════════════════════════════════════
    echo ""
    echo "━━━ Configuring hotspot via NetworkManager ━━━"

    # Remove any previous GarbageBot connection
    nmcli connection delete "$NM_CON_NAME" 2>/dev/null || true

    # Also clean up any leftover hostapd/dnsmasq from failed attempts
    systemctl stop hostapd 2>/dev/null || true
    systemctl disable hostapd 2>/dev/null || true
    systemctl stop dnsmasq 2>/dev/null || true
    systemctl disable dnsmasq 2>/dev/null || true
    rm -f /etc/NetworkManager/conf.d/99-garbagebot-unmanaged.conf

    # Ensure NM manages wlan0
    systemctl restart NetworkManager
    sleep 2

    # Create a persistent WiFi AP connection via NetworkManager
    # ipv4.method=shared enables NM's built-in DHCP server (dnsmasq)
    nmcli connection add \
        type wifi \
        ifname "$WLAN_IFACE" \
        con-name "$NM_CON_NAME" \
        autoconnect yes \
        ssid "$SSID" \
        wifi.mode ap \
        wifi.band bg \
        wifi.channel 1 \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$PASSWORD" \
        ipv4.method shared \
        ipv4.addresses "$AP_IP/24" \
        ipv6.method ignore \
        connection.autoconnect-priority 100

    ok "NetworkManager AP connection '$NM_CON_NAME' created"

    # Activate the hotspot now
    echo "Activating hotspot..."
    nmcli connection up "$NM_CON_NAME" 2>/dev/null && \
        ok "Hotspot is LIVE" || \
        warn "Could not activate hotspot immediately — will activate on next boot"

    # Verify
    sleep 3
    if nmcli -t -f GENERAL.STATE connection show "$NM_CON_NAME" 2>/dev/null | grep -qi "activated"; then
        ok "Hotspot verified: $SSID is broadcasting"
        HOTSPOT_OK=true
    else
        warn "Hotspot may not be active yet — check: nmcli connection show '$NM_CON_NAME'"
        HOTSPOT_OK=false
    fi

else
    # ═══════════════════════════════════════════════════════════════
    # dhcpcd method (Bullseye and older)
    #
    # Uses traditional hostapd + dnsmasq setup.
    # ═══════════════════════════════════════════════════════════════
    echo ""
    echo "━━━ Step 1/4: Installing hostapd and dnsmasq ━━━"

    apt-get update -qq
    apt-get install -y hostapd dnsmasq

    systemctl stop hostapd 2>/dev/null || true
    systemctl stop dnsmasq  2>/dev/null || true
    ok "Packages installed"

    # ── Static IP via dhcpcd ──
    echo ""
    echo "━━━ Step 2/4: Configuring static IP ($AP_IP) ━━━"

    sed -i '/# GarbageBot Hotspot Config/,/# End GarbageBot/d' /etc/dhcpcd.conf

    cat >> /etc/dhcpcd.conf << EOF
# GarbageBot Hotspot Config
interface $WLAN_IFACE
    static ip_address=$AP_IP/24
    nohook wpa_supplicant
# End GarbageBot
EOF
    systemctl restart dhcpcd
    ok "Static IP $AP_IP assigned via dhcpcd"

    # ── dnsmasq (DHCP server) ──
    echo ""
    echo "━━━ Step 3/4: Configuring DHCP server ━━━"

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

    # ── hostapd (Access Point) ──
    echo ""
    echo "━━━ Step 4/4: Configuring and starting Access Point ━━━"

    cat > /etc/hostapd/hostapd.conf << EOF
# GarbageBot WiFi Access Point — Pi 4B (Open)
interface=$WLAN_IFACE
driver=nl80211
ssid=$SSID
country_code=$COUNTRY
hw_mode=g
channel=1
auth_algs=1
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
macaddr_acl=0
ignore_broadcast_ssid=0
EOF

    if [ -f /etc/default/hostapd ]; then
        sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd
    fi

    systemctl unmask hostapd
    systemctl enable hostapd dnsmasq
    systemctl restart dnsmasq
    systemctl restart hostapd

    sleep 3
    HOTSPOT_OK=false
    systemctl is-active --quiet hostapd && systemctl is-active --quiet dnsmasq && HOTSPOT_OK=true

    if $HOTSPOT_OK; then
        ok "hostapd + dnsmasq running — hotspot is LIVE"
    else
        warn "Service startup issue — check: sudo journalctl -u hostapd -n 20"
    fi
fi

# ─── Summary ───
echo ""
echo "══════════════════════════════════════════"
echo "  ✅ WiFi Hotspot configured!"
echo ""
printf "  Network:   %s\n" "$SSID"
printf "  Password:  %s\n" "$PASSWORD"
printf "  Country:   %s\n" "$COUNTRY"
echo "  Dashboard: http://$AP_IP:5000"
echo ""
echo "  Connect your phone/laptop to '$SSID'"
echo "  Then open http://$AP_IP:5000"
echo ""
if $USE_NM; then
    echo "  Method: NetworkManager native AP (auto-starts on boot)"
    echo ""
    echo "  To undo: sudo nmcli connection delete '$NM_CON_NAME'"
else
    echo "  Method: hostapd + dnsmasq"
fi
echo "══════════════════════════════════════════"
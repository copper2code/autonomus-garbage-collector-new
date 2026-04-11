#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# setup_hotspot.sh — Repurposed to connect Pi to Home WiFi natively
# ═══════════════════════════════════════════════════════════════════

set -e

SSID="${1:-YOUR_WIFI_NAME}"
PASSWORD="${2:-YOUR_WIFI_PASSWORD}"
WLAN_IFACE="wlan0"

# ─── Colour helpers ───
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
die()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "══════════════════════════════════════════"
echo "  🤖 Garbage Collector — Home WiFi Setup"
echo "══════════════════════════════════════════"
echo "  Connecting to:"
echo "  SSID:        $SSID"
echo "  Password:    $PASSWORD"
echo "══════════════════════════════════════════"
echo ""

[ "$EUID" -ne 0 ] && die "Please run with sudo"

echo "━━━ Performing Network Factory Reset ━━━"
# 1. PURGE HOSTAPD AND DNSMASQ completely!
apt-get purge -y hostapd dnsmasq 2>/dev/null || true
rm -rf /etc/hostapd /etc/dnsmasq.conf*
rm -f /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf
rm -f /etc/NetworkManager/conf.d/99-garbagebot-unmanaged.conf

# 2. CLEAR DHCPCD.CONF
if [ -f /etc/dhcpcd.conf ]; then
    sed -i '/# GarbageBot Hotspot Config/,/# End GarbageBot/d' /etc/dhcpcd.conf
    systemctl restart dhcpcd 2>/dev/null || true
fi

# Ensure Wi-Fi is physically unblocked
rfkill unblock wifi 2>/dev/null || true
sleep 2

if command -v nmcli &>/dev/null; then
    echo "━━━ Connecting via NetworkManager ━━━"
    # Delete any old hotspot or conflicting profiles
    nmcli connection delete GarbageBot-AP 2>/dev/null || true
    
    # Connect directly to the user's home router
    nmcli device wifi connect "$SSID" password "$PASSWORD" name "HomeWiFi" || \
        warn "Could not connect immediately. Ensure the SSID and Password are correct!"
    
    ok "NetworkManager configured for client mode"
else
    echo "━━━ Connecting via wpa_supplicant ━━━"
    # Ensure wpa_supplicant is managing it properly
    sed -i '/network={/,/}/d' /etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null || true
    wpa_passphrase "$SSID" "$PASSWORD" >> /etc/wpa_supplicant/wpa_supplicant.conf
    
    # Restart interface to apply
    ifconfig "$WLAN_IFACE" down || true
    ifconfig "$WLAN_IFACE" up || true
    wpa_cli -i "$WLAN_IFACE" reconfigure || true
    ok "wpa_supplicant updated"
fi

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ Wi-Fi Client Setup Complete!"
echo "  The Pi should now connect to your router."
echo "  Use 'hostname -I' to find its new IP address"
echo "  and navigate to http://<NEW_IP>:5000 in your browser."
echo "══════════════════════════════════════════"
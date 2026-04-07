#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# setup_hotspot.sh — Configure Raspberry Pi 4B as a WiFi Access Point
#
# Creates a WiFi hotspot so you can connect directly to the robot
# and access the dashboard at http://192.168.4.1:5000
#
# Usage:  sudo ./setup_hotspot.sh [SSID] [PASSWORD]
# Default: SSID=GarbageBot  PASSWORD=robot1234
# ═══════════════════════════════════════════════════════════════════

set -e

SSID="${1:-GarbageBot}"
PASSWORD="${2:-robot1234}"
AP_IP="192.168.4.1"
DHCP_RANGE_START="192.168.4.10"
DHCP_RANGE_END="192.168.4.50"
WLAN_IFACE="wlan0"

echo "══════════════════════════════════════════"
echo "  🤖 Garbage Collector — WiFi Hotspot Setup"
echo "══════════════════════════════════════════"
echo "  SSID:     $SSID"
echo "  Password: $PASSWORD"
echo "  IP:       $AP_IP"
echo "  Interface: $WLAN_IFACE"
echo "══════════════════════════════════════════"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo: sudo ./setup_hotspot.sh"
    exit 1
fi

# ─── 1. Install required packages ───
echo "📦 Installing hostapd and dnsmasq..."
apt update -qq
apt install -y hostapd dnsmasq

# Stop services during config
systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true

# ─── 2. Configure dhcpcd (static IP for wlan0) ───
echo "📝 Configuring static IP..."

# Remove any previous config we added
sed -i '/# GarbageBot Hotspot Config/,/# End GarbageBot/d' /etc/dhcpcd.conf

cat >> /etc/dhcpcd.conf << EOF
# GarbageBot Hotspot Config
interface $WLAN_IFACE
    static ip_address=$AP_IP/24
    nohook wpa_supplicant
# End GarbageBot
EOF

# ─── 3. Configure dnsmasq (DHCP server) ───
echo "📝 Configuring DHCP server..."

# Backup original if exists
[ -f /etc/dnsmasq.conf ] && [ ! -f /etc/dnsmasq.conf.orig ] && \
    cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig

cat > /etc/dnsmasq.conf << EOF
# GarbageBot DHCP Configuration
interface=$WLAN_IFACE
dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,255.255.255.0,24h
domain=local
address=/garbagebot.local/$AP_IP
EOF

# ─── 4. Configure hostapd (Access Point) ───
echo "📝 Configuring WiFi Access Point..."

cat > /etc/hostapd/hostapd.conf << EOF
# GarbageBot WiFi Access Point
interface=$WLAN_IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=IN
EOF

# Tell hostapd where its config is
sed -i 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd 2>/dev/null || true

# ─── 5. Enable and start services ───
echo "🚀 Enabling services..."
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq

# ─── 6. Restart networking ───
echo "🔄 Restarting services..."
systemctl restart dhcpcd
systemctl restart dnsmasq
systemctl restart hostapd

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ WiFi Hotspot configured!"
echo ""
echo "  Network:   $SSID"
echo "  Password:  $PASSWORD"
echo "  Dashboard: http://$AP_IP:5000"
echo ""
echo "  Connect your phone/laptop to '$SSID'"
echo "  Then open http://$AP_IP:5000"
echo "══════════════════════════════════════════"

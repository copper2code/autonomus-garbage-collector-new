# Hardware Setup & Installation Guide — Raspberry Pi 4B

This document provides complete hardware assembly and software installation instructions for the Autonomous Garbage Collector Robot on **Raspberry Pi 4 Model B**.

---

## Quick Start (TL;DR)

```bash
# On a fresh Raspberry Pi 4B with Raspberry Pi OS (64-bit):
git clone https://github.com/rakesh-i/ESP32-Autonomous-car
cd ESP32-Autonomous-car
chmod +x install.sh
sudo ./install.sh
sudo reboot
```

After reboot:
1. Connect your phone/laptop to WiFi network **"GarbageBot"** (password: `robot1234`)
2. Open browser → **http://192.168.4.1:5000**
3. Done! Configure everything from the dashboard.

---

## 1. Hardware Assembly

### Power Architecture

```
[12V Battery Pack]
       │
       ├──→ L298N Motor Driver (VCC) → Powers 2× DC Motors
       │
       └──→ LM2596 Buck Converter (set to 5V output)
                │
                ├──→ Arduino 1 (Vin)
                ├──→ Arduino 2 (Vin)
                ├──→ 3× ULN2003 Boards (VCC)
                └──→ Servo Motor (VCC, red wire)

[Raspberry Pi 4B]
       │
       └──→ Powered by its own 5V/3A USB-C adapter
```

> ⚠️ **CRITICAL:** All GND lines from every component MUST be connected together. Floating grounds cause erratic behavior, servo jitter, and serial communication failures.

### Arduino 1 — Car Base Wiring (L298N)

| Arduino Pin | L298N Pin | Wire Color (suggested) |
|:-----------:|:---------:|:----------------------:|
| 9 | ENA | Yellow |
| 8 | IN1 | Orange |
| 7 | IN2 | Orange |
| 5 | IN3 | Blue |
| 4 | IN4 | Blue |
| 3 | ENB | Yellow |
| GND | GND | Black |

**L298N to Motors:**
- OUT1 + OUT2 → Left DC Motor
- OUT3 + OUT4 → Right DC Motor
- 12V terminal → Battery positive
- GND terminal → Battery negative + Arduino GND

### Arduino 2 — Robotic Arm Wiring

**Base Stepper (ULN2003 Board 1):**
| Arduino Pin | ULN2003 Pin |
|:-----------:|:-----------:|
| 2 | IN1 |
| 3 | IN2 |
| 4 | IN3 |
| 5 | IN4 |

**Joint Stepper (ULN2003 Board 2):**
| Arduino Pin | ULN2003 Pin |
|:-----------:|:-----------:|
| 6 | IN1 |
| 7 | IN2 |
| 8 | IN3 |
| 9 | IN4 |

**Extension Stepper (ULN2003 Board 3):**
| Arduino Pin | ULN2003 Pin |
|:-----------:|:-----------:|
| 10 | IN1 |
| 11 | IN2 |
| 12 | IN3 |
| 13 | IN4 |

**Clamp Servo:**
| Servo Wire | Connection |
|:----------:|:----------:|
| Signal (Orange/Yellow) | Arduino pin A0 |
| VCC (Red) | 5V from buck converter (NOT Arduino 5V) |
| GND (Brown/Black) | Common GND bus |

> 💡 **Tip:** Add a 470µF electrolytic capacitor across the servo's VCC and GND to reduce jitter.

### Camera Mounting
- Mount the USB webcam on the arm, positioned after (below) the clamp mechanism.
- Route the USB cable along the arm and chassis, leaving slack for arm movement.
- Plug into any USB port on the Raspberry Pi 4B.

---

## 2. Arduino Firmware Upload

### How Auto-Identification Works

Both Arduinos now **broadcast their identity on startup**:
- **Car Arduino** continuously sends `{"id":"car"}` every 500ms
- **Arm Arduino** continuously sends `{"id":"arm"}` every 500ms

When the Raspberry Pi boots, it scans all serial ports, listens for these broadcasts, sends `{"cmd":"ack"}` to confirm each Arduino, and automatically assigns the correct port. **No manual port configuration needed!**

### Prerequisites
- Install [Arduino IDE](https://www.arduino.cc/en/software) (v2.0+ recommended)
- Install the **ArduinoJson** library:
  - Open Arduino IDE → Tools → Manage Libraries
  - Search for "ArduinoJson" by Benoit Blanchon
  - Click Install

### Upload Car Firmware (Arduino 1)
1. Connect Arduino 1 to your computer via USB
2. Open `arduino/car_control/car_control.ino`
3. Select your board (Tools → Board → Arduino Uno)
4. Select the correct port (Tools → Port)
5. Click Upload (→ button)

### Upload Arm Firmware (Arduino 2)
1. Connect Arduino 2 to your computer via USB
2. Open `arduino/arm_control/arm_control.ino`
3. Select your board and port
4. Click Upload

### Verify
Open Serial Monitor (115200 baud). You should see the Arduino repeatedly printing:
```json
{"id":"car"}
```
or
```json
{"id":"arm"}
```
This means it's waiting for the Pi to acknowledge it. Send `{"cmd":"ack"}` and you should see `{"status":"ok","msg":"car identified"}`.

---

## 3. Raspberry Pi 4B Software Setup

### Option A: Automated Install (Recommended)

```bash
# 1. Flash Raspberry Pi OS (64-bit / Bookworm) to an SD card
# 2. Boot the Pi and connect via SSH or monitor
# 3. Clone and install:

git clone https://github.com/rakesh-i/ESP32-Autonomous-car
cd ESP32-Autonomous-car

chmod +x install.sh
sudo ./install.sh
```

The installer will:
- ✅ Install all system dependencies (libatlas, v4l-utils, etc.)
- ✅ Create a Python virtual environment
- ✅ Install PyTorch ARM64 wheel (CPU-only, optimized for Pi 4B)
- ✅ Install all pip requirements
- ✅ Create a WiFi hotspot (SSID: **GarbageBot**, Password: **robot1234**)
- ✅ Set up auto-start on boot via systemd
- ✅ Configure serial port permissions

After install:
```bash
sudo reboot
```

### Option B: Manual Install

```bash
# System Dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev \
    libatlas-base-dev libopenjp2-7 libtiff5 \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev v4l-utils git

# Clone project
git clone https://github.com/rakesh-i/ESP32-Autonomous-car
cd ESP32-Autonomous-car

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Install PyTorch for ARM64 (Pi 4B)
pip install -U pip setuptools wheel
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining packages
pip install -r requirements.txt

# Run
python main.py
```

### WiFi Hotspot Setup (Standalone)

If you only need to set up the hotspot separately:
```bash
chmod +x setup_hotspot.sh
sudo ./setup_hotspot.sh GarbageBot robot1234
```

---

## 4. Connecting to the Robot

### Via WiFi Hotspot (Primary — No SSH Needed!)

1. Power on the Raspberry Pi 4B
2. Wait ~30 seconds for boot
3. On your phone or laptop, connect to WiFi:
   - **Network:** `GarbageBot`
   - **Password:** `robot1234`
4. Open browser: **http://192.168.4.1:5000**
5. Use the **Settings** tab to configure camera, serial ports, speeds, etc.

### First-Time Setup via Dashboard

1. Go to ⚙️ **Settings** tab
2. Camera should auto-detect. Click **🔍 Scan** if not → select camera → **📸 Test**
3. Serial ports are auto-detected via identity protocol. Check **📊 Diagnostics** to verify
4. Go to **🔧 Arm Calibration** → click **🔄 Reset Arm to Home** to verify arm moves correctly
5. Adjust motor speeds if needed
6. Click **💾 Save All Settings**

### Auto-Identification Flow

When the Pi starts:
```
Pi scans /dev/ttyUSB* and /dev/ttyACM*
  │
  ├── Opens /dev/ttyUSB0 → listens...
  │     Arduino 1 screams: {"id":"car"}
  │     Pi sends: {"cmd":"ack"}
  │     Arduino confirms: {"status":"ok","msg":"car identified"}
  │     ✓ /dev/ttyUSB0 = Car Arduino
  │
  └── Opens /dev/ttyUSB1 → listens...
        Arduino 2 screams: {"id":"arm"}
        Pi sends: {"cmd":"ack"}
        Arduino confirms: {"status":"ok","msg":"arm identified"}
        ✓ /dev/ttyUSB1 = Arm Arduino
```

No more guessing which port is which!

---

## 5. Running the Robot

### Auto-start (Default after install.sh)

The robot starts automatically on boot. Manage via:
```bash
# Check status
sudo systemctl status garbagebot

# View logs
sudo journalctl -u garbagebot -f

# Restart
sudo systemctl restart garbagebot

# Stop
sudo systemctl stop garbagebot

# Disable auto-start
sudo systemctl disable garbagebot
```

### Manual Start

```bash
cd /path/to/ESP32-Autonomous-car
source venv/bin/activate
python main.py
```

Expected output:
```
╔══════════════════════════════════════════════════╗
║   🤖 Autonomous Garbage Collector Robot v2.0    ║
║   Platform: Raspberry Pi 4B                      ║
╚══════════════════════════════════════════════════╝

━━━ Initializing Serial Manager ━━━
🔍 Auto-detecting Arduinos (listening for identity broadcasts)...
Found serial ports: ['/dev/ttyUSB0', '/dev/ttyUSB1']
🔍 Port /dev/ttyUSB0 identifies as: CAR
✓ CAR Arduino confirmed on /dev/ttyUSB0
🔍 Port /dev/ttyUSB1 identifies as: ARM
✓ ARM Arduino confirmed on /dev/ttyUSB1
━━━ Serial Discovery Complete ━━━

─── System Status ───
  Car Arduino:  ✓ Connected (/dev/ttyUSB0)
  Arm Arduino:  ✓ Connected (/dev/ttyUSB1)
  Camera:       ✓ Running
  Dashboard:    http://192.168.4.1:5000
```

---

## 6. Troubleshooting

### Camera Not Working
- Run `ls /dev/video*` to check if the webcam is detected
- Try different camera indices in the Settings dashboard (⚙️ → Camera → Scan)
- Some webcams need: `sudo modprobe bcm2835-v4l2`
- Check `v4l2-ctl --list-devices` for available cameras

### Arduino Not Detected
- Run `ls /dev/ttyUSB* /dev/ttyACM*` to see available ports
- Open Arduino IDE Serial Monitor (115200 baud) — you should see `{"id":"car"}` or `{"id":"arm"}`
- If you see nothing, re-upload the firmware
- Check permissions: `sudo usermod -aG dialout $USER` then reboot
- Override in Settings if auto-detect fails

### PyTorch Won't Install
- Ensure you're using **64-bit** Raspberry Pi OS (not 32-bit)
- Use the specific ARM64 wheel URL:
  ```bash
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  ```
- If memory errors occur during install, increase swap:
  ```bash
  sudo dphys-swapfile swapoff
  sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
  ```

### WiFi Hotspot Not Appearing
- Check hostapd status: `sudo systemctl status hostapd`
- Check config: `cat /etc/hostapd/hostapd.conf`
- Ensure WiFi isn't blocked: `sudo rfkill unblock wifi`
- Re-run: `sudo ./setup_hotspot.sh`

### Dashboard Not Loading
- Check if the service is running: `sudo systemctl status garbagebot`
- Try manual start to see errors: `python main.py`
- Verify IP: `hostname -I` should show `192.168.4.1`

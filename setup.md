# Hardware Setup & Installation Guide

This document provides detailed hardware assembly and software installation instructions for the Autonomous Garbage Collector Robot.

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

[Raspberry Pi]
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
- Plug into any USB port on the Raspberry Pi.

---

## 2. Arduino Firmware Upload

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
Open Serial Monitor (115200 baud) and send:
```json
{"cmd": "move", "dir": "forward", "speed": 100}
```
The car motors should spin. Send `{"cmd": "move", "dir": "stop", "speed": 0}` to stop.

---

## 3. Raspberry Pi Software Setup

### System Prerequisites
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

### Project Installation
```bash
git clone https://github.com/rakesh-i/ESP32-Autonomous-car
cd ESP32-Autonomous-car

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### Identify Arduino Ports
With both Arduinos plugged into the Pi via USB:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```
You should see two ports (e.g., `/dev/ttyUSB0` and `/dev/ttyUSB1`).

To identify which is which, unplug one Arduino and check which port disappears:
```bash
# Unplug Arduino 1 (car), check what's left
ls /dev/ttyUSB*
# The remaining port is Arduino 2 (arm)
```

Update `config.py` accordingly:
```python
CAR_SERIAL_PORT = "/dev/ttyUSB0"   # Whichever port is Arduino 1
ARM_SERIAL_PORT = "/dev/ttyUSB1"   # Whichever port is Arduino 2
```

### Optional: Create Persistent Port Names with udev
Create `/etc/udev/rules.d/99-robot-arduinos.rules`:
```
SUBSYSTEM=="tty", ATTRS{serial}=="YOUR_ARDUINO1_SERIAL", SYMLINK+="arduino_car"
SUBSYSTEM=="tty", ATTRS{serial}=="YOUR_ARDUINO2_SERIAL", SYMLINK+="arduino_arm"
```
Then use `/dev/arduino_car` and `/dev/arduino_arm` in config.py.

---

## 4. Running the System

```bash
cd /path/to/ESP32-Autonomous-car
source venv/bin/activate
python main.py
```

Expected output:
```
2026-03-28 20:00:00 - INFO - Connected to Arduino on /dev/ttyUSB0
2026-03-28 20:00:02 - INFO - Connected to Arduino on /dev/ttyUSB1
2026-03-28 20:00:02 - INFO - Camera started on index 0
2026-03-28 20:00:02 - INFO - Starting Web Server on 0.0.0.0:5000
```

Open your browser: `http://<PI_IP>:5000`

### Auto-start on Boot (Optional)
Create a systemd service:
```bash
sudo nano /etc/systemd/system/robot.service
```

```ini
[Unit]
Description=Garbage Collector Robot
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/ESP32-Autonomous-car
ExecStart=/home/pi/ESP32-Autonomous-car/venv/bin/python main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable robot.service
sudo systemctl start robot.service
```

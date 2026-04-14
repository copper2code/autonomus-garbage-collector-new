<!-- PROJECT LOGO -->
<br />
<p align="center">
  <h1 align="center">🤖 Autonomous Garbage Collector Robot</h1>
  <p align="center">
    A Raspberry Pi + Dual-Arduino robotic platform with CNN-powered autonomous driving and intelligent garbage bin collection.
    <br />
    <br />
    <a href="#getting-started"><strong>Get Started »</strong></a>
    ·
    <a href="#how-it-works">How It Works</a>
    ·
    <a href="#training-the-ai">Train the AI</a>
    ·
    <a href="#command-protocol">Protocol Docs</a>
  </p>
</p>

---

## Table of Contents

- [About The Project](#about-the-project)
- [System Architecture](#system-architecture)
- [Hardware Requirements](#hardware-requirements)
- [Wiring Diagram](#wiring-diagram)
- [Software Stack](#software-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [How It Works](#how-it-works)
- [Training the AI](#training-the-ai)
- [Web Dashboard](#web-dashboard)
- [Command Protocol](#command-protocol)
- [Troubleshooting](#troubleshooting)
- [Legacy Code](#legacy-code)
- [Contributing](#contributing)
- [Contact](#contact)
- [References](#references)

---

## About The Project



This project builds a fully autonomous mobile robot capable of:

1. **Self-driving** — using a CNN (Convolutional Neural Network) trained from your own manual driving data.
2. **Garbage bin detection & collection** — a second CNN runs simultaneously to spot garbage bins. When one is found, the robot stops, the robotic arm grabs the bin, dumps its contents into the onboard storage, places the bin back on the ground, and resumes driving.

The entire system is controlled through a **real-time web dashboard** accessible from any device on the same WiFi network — no app installation needed.

### What Makes This Different

| Feature | This Project | Typical Hobby Robots |
|---------|-------------|---------------------|
| Navigation | End-to-end CNN (learns from YOU) | Hardcoded PID / line sensor |
| Object Interaction | Full grab-dump-replace arm sequence | None or basic push |
| Training | Drive from browser → auto-trains model | Manual scripts, numpy arrays |
| Control | Web dashboard with live video HUD | Serial terminal or IR remote |
| Architecture | Raspberry Pi + 2× Arduino (distributed) | Single microcontroller |

### Built With

* [Python 3](https://www.python.org/) — Main application logic
* [PyTorch](https://pytorch.org/) — Dual CNN models (driving + bin detection)
* [OpenCV](https://opencv.org/) — Camera capture and MJPEG streaming
* [Flask](https://flask.palletsprojects.com/) — Web dashboard and REST API
* [Arduino](https://www.arduino.cc/) — Motor and arm firmware
* [ArduinoJson](https://arduinojson.org/) — Structured serial communication

---

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    RASPBERRY PI (Brain)                   │
│                                                          │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │ Flask Web │  │ Driving CNN │  │ Bin Detector CNN  │    │
│  │ Dashboard │  │ (PyTorch)   │  │ (PyTorch)         │    │
│  └─────┬────┘  └──────┬──────┘  └────────┬─────────┘    │
│        │               │                  │              │
│  ┌─────┴───────────────┴──────────────────┴──────────┐   │
│  │              main.py — State Machine               │   │
│  │     MANUAL ←→ TRAINING ←→ AUTONOMOUS              │   │
│  └──────────┬─────────────────────────┬──────────────┘   │
│             │ USB Serial (JSON)       │ USB Serial (JSON) │
└─────────────┼─────────────────────────┼──────────────────┘
              │                         │
    ┌─────────▼─────────┐    ┌─────────▼──────────────┐
    │   ARDUINO 1       │    │   ARDUINO 2             │
    │   Car Motors      │    │   Robotic Arm           │
    │                   │    │                         │
    │  L298N Driver     │    │  3× ULN2003 Drivers    │
    │  2× DC Motors     │    │  3× 28BYJ-48 Steppers  │
    │                   │    │  1× Servo (Clamp)      │
    │  Watchdog: 1s     │    │  + USB Camera on arm   │
    └───────────────────┘    └─────────────────────────┘
```

### Why Three Processors?

- **Raspberry Pi** handles computationally expensive tasks: video processing, neural network inference, web serving.
- **Arduino 1** handles real-time PWM motor control for driving, with a hardware watchdog that stops the car if the Pi crashes.
- **Arduino 2** handles precise stepper motor timing (half-step sequences) for the robotic arm and servo clamp.

---

## Hardware Requirements

### Components List

| Component | Quantity | Purpose |
|-----------|----------|---------|
| Raspberry Pi 4/5 | 1 | Main controller |
| Arduino UNO/Nano | 2 | Motor + Arm controllers |
| USB Webcam (1080p) | 1 | Vision (mounted on arm) |
| L298N Motor Driver | 1 | DC motor control for car |
| DC Gear Motors (3-12V) | 2 | Car wheels |
| ULN2003 Driver Board | 3 | Stepper motor drivers |
| 28BYJ-48 Stepper Motor | 3 | Arm: Base, Joint, Extension |
| SG90 Servo Motor | 1 | Arm: Clamp mechanism |
| Car Chassis with Wheels | 1 | Robot base |
| USB-A to USB-B Cables | 2 | Pi ↔ Arduino connections |
| 12V Battery Pack | 1 | Motors power supply |
| 5V Buck Converter (LM2596) | 1 | Arduino/Servo power |
| Jumper Wires | ~40 | Connections |

### Robotic Arm Configuration

```
         [USB Camera]
              │
        ┌─────┴─────┐
        │  CLAMP     │ ← SG90 Servo (open/close/dump-tilt)
        │  (Servo)   │
        └─────┬──────┘
              │
     ┌────────┴────────┐
     │   EXTENSION     │ ← 28BYJ-48 Stepper 3 (extend/retract reach)
     │   (Stepper 3)   │
     └────────┬────────┘
              │
     ┌────────┴────────┐
     │   JOINT         │ ← 28BYJ-48 Stepper 2 (raise/lower arm)
     │   (Stepper 2)   │
     └────────┬────────┘
              │
     ┌────────┴────────┐
     │   BASE          │ ← 28BYJ-48 Stepper 1 (rotate left/right)
     │   (Stepper 1)   │
     └────────┴────────┘
              │
        [Car Chassis]
```

---

## Wiring Diagram

### Arduino 1 — Car Base (L298N)

| Arduino Pin | L298N Pin | Function |
|:-----------:|:---------:|----------|
| 9 | ENA | Left motor speed (PWM) |
| 8 | IN1 | Left motor direction 1 |
| 7 | IN2 | Left motor direction 2 |
| 5 | IN3 | Right motor direction 1 |
| 4 | IN4 | Right motor direction 2 |
| 3 | ENB | Right motor speed (PWM) |
| GND | GND | Common ground |

### Arduino 2 — Robotic Arm (ULN2003 + Servo)

| Arduino Pin | Component | Function |
|:-----------:|:---------:|----------|
| 2, 3, 4, 5 | ULN2003 Board 1 | Base stepper (IN1–IN4) |
| 6, 7, 8, 9 | ULN2003 Board 2 | Joint stepper (IN1–IN4) |
| 10, 11, 12, 13 | ULN2003 Board 3 | Extension stepper (IN1–IN4) |
| A0 | Servo signal wire | Clamp servo PWM |
| GND | All boards GND | Common ground |

> ⚠️ **IMPORTANT:** Do NOT power stepper motors or servos from the Arduino 5V pin. Use a separate 5V/3A power supply. Connect all grounds together (Arduino + Drivers + Battery).

---

## Software Stack

```
Python 3.9+
├── flask          — Web server and REST API
├── flask-cors     — Cross-origin support
├── pyserial       — Arduino serial communication
├── opencv-python  — Camera capture and MJPEG streaming
├── torch          — CNN model training and inference
├── torchvision    — Image transforms and augmentation
├── numpy          — Array operations
├── Pillow         — Image format conversion
└── tqdm           — Training progress bars

Arduino Libraries
├── ArduinoJson    — JSON command parsing
└── Servo.h        — PWM servo control (built-in)
```

---

## Project Structure

```
├── main.py                          # System entry point and state machine
├── config.py                        # All configurable parameters
├── requirements.txt                 # Python dependencies
├── setup.md                         # Hardware setup instructions
│
├── communication/
│   └── arduino_serial.py            # Thread-safe serial manager (auto-reconnect)
│
├── control/
│   ├── motor_control.py             # Car DC motor abstraction
│   └── arm_control.py               # Arm stepper/servo + collection sequence
│
├── vision/
│   ├── camera_stream.py             # OpenCV capture + MJPEG generator
│   ├── line_detection.py            # Legacy OpenCV PID line follower
│   ├── model_inference.py           # Dual-CNN inference engine (PyTorch)
│   └── data_recorder.py             # Saves frames during training mode
│
├── ml/
│   └── training_pipeline.py         # CompactCNN definition + auto-trainer
│
├── server/
│   ├── web_interface.py             # Flask API routes
│   └── templates/
│       └── dashboard.html           # Responsive web control panel
│
├── arduino/
│   ├── car_control/
│   │   └── car_control.ino          # Arduino 1 firmware (L298N DC motors)
│   └── arm_control/
│       └── arm_control.ino          # Arduino 2 firmware (ULN2003 steppers + servo)
│
├── models/                          # Auto-created: saved .pth model weights
├── data/                            # Auto-created: training images
│   └── driving/
│       ├── forward/
│       ├── left/
│       ├── right/
│       └── stop/
│
├── Client/                          # [Legacy] Original ESP32 keyboard client
├── Training/                        # [Legacy] Original TFLearn/AlexNet training
├── OpenCV Line Follower and Trainer/# [Legacy] Original PID line follower
└── Files for esp32/                 # [Legacy] Original ESP32 MicroPython firmware
```

---

## Getting Started

### 1. Flash the Arduinos

1. Open the Arduino IDE and install the **ArduinoJson** library (Library Manager → search "ArduinoJson" → Install).
2. Open `arduino/car_control/car_control.ino`, select your board and port, and upload to **Arduino 1**.
3. Open `arduino/arm_control/arm_control.ino`, select your board and port, and upload to **Arduino 2**.

### 2. Set Up the Raspberry Pi

```bash
# Clone the repository
git clone https://github.com/rakesh-i/ESP32-Autonomous-car
cd ESP32-Autonomous-car

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

Edit `config.py` to match your hardware:

```python
# Most important: make sure these match your USB port assignment
CAR_SERIAL_PORT   = "/dev/ttyUSB0"   # Arduino 1 (car motors)
ARM_SERIAL_PORT   = "/dev/ttyUSB1"   # Arduino 2 (arm)

# Camera index (usually 0 for the first USB webcam)
CAMERA_INDEX = 0
```

> 💡 **Tip:** If the car moves when you send arm commands (or vice versa), swap the two port values.

### 4. Run

```bash
python main.py
```

Open a browser on any device on the same network and go to:

```
http://<RASPBERRY_PI_IP>:5000
```

---

## How It Works

### Operating Modes

The system has three modes, switchable from the web dashboard:

#### 1. Manual Mode (Default)
You drive the car and control the arm directly from the web dashboard using keyboard (`W A S D`) or onscreen buttons. **Hold-to-move**: The car will continue moving after you press a direction. You must explicitly press the **STOP** button (or the `Spacebar`) to halt the car.

#### 2. Training Mode
While in this mode, every camera frame is saved to disk labeled with your current steering input. This creates the training dataset for the Driving CNN.

**When you exit Training Mode**, the system automatically:
1. Launches background PyTorch training (visible as a yellow progress bar on the video feed)
2. Trains the CompactCNN on your collected data (~10 epochs)
3. Saves the model to `models/driving_model.pth`
4. Hot-reloads the model into memory (no restart needed)
5. Shows a green "Model Ready" notification on the dashboard

#### 3. Autonomous Mode
Two PyTorch CNNs run simultaneously on each camera frame:

```
Camera Frame
    │
    ├──→ [Driving CNN] → "forward" / "left" / "right" / "stop" → Arduino 1 (motors)
    │
    └──→ [Bin Detector CNN] → "garbage_bin" detected?
                                    │
                                    YES → Stop car → Execute ARM_COLLECT_SEQUENCE
                                    │
                                    └── Grab → Lift → Swing → Dump → Replace → Release → Home
                                              │
                                              └── Resume Driving CNN
```

### The Garbage Bin Collection Sequence

When the Bin Detector CNN spots a garbage bin with >85% confidence:

| Step | Action | Details |
|------|--------|---------|
| 1 | Open clamp | Servo → 10° |
| 2 | Extend + Lower | Extension stepper forward, Joint stepper down |
| 3 | Grab bin | Servo → 70° (clamp shut) |
| 4 | Lift | Joint stepper up (200 steps) |
| 5 | Swing to storage | Base stepper rotates 180 steps |
| 6 | Dump contents | Servo → 170° (tilt clamp upside-down) |
| 7 | Level clamp | Servo → 70° |
| 8 | Swing back | Base stepper rotates 180 steps back |
| 9 | Lower to ground | Joint stepper down |
| 10 | Release bin | Servo → 10° (open) |
| 11 | Return home | Extension retracts, Joint lifts |

All step counts and angles are configurable in `config.py` → `ARM_COLLECT_SEQUENCE`.

---

## Training the AI

### Training the Driving Model

1. Open the dashboard at `http://<PI_IP>:5000`
2. Click **"Training Mode (Record Data)"**
3. Drive the car around your track using `W A S D` keys for ~3–5 minutes
4. Click **"Manual Mode"** to stop recording
5. Watch the yellow "Compiling..." bar on the video feed
6. When you see the green "Model Ready" notification, switch to **"Autonomous System"**

> 💡 **Tips for better training:**
> - Drive smoothly — avoid jerky corrections
> - Cover the full track 3–5 times
> - Include recovery: intentionally veer off and correct back
> - More data = better model. 2000+ frames recommended.

### Training the Bin Detector Model

The bin detector uses the same `CompactCNN` architecture. To train it:

1. Collect images of garbage bins and background scenes
2. Organize them into `data/bin_training/background/` and `data/bin_training/garbage_bin/`
3. Modify `ml/training_pipeline.py` to point to your bin data directory and update the classes list
4. Run training and save to `models/garbage_bin.pth`

### PC Simulation and Arm Testing

To test target locking and the robotic arm without running the full Raspberry Pi dashboard, you can use the `pc_arm_test.py` script directly on your computer:

```bash
python pc_arm_test.py
```

This visualization includes a custom HUD:
- A **center screen crosshair** (white) indicating straight-ahead view.
- A **tracking target dot** (red) centered on the detected bin.
- A **tracking line** (yellow) linking the center to the target.

When the bin is perfectly locked via the CNN, this script will dynamically connect to the Arduino (if plugged into the PC via USB) and trigger the entire robotic arm grab-and-dump sequence automatically.

---

## Web Dashboard

The dashboard is a responsive dark-mode web interface accessible from any browser:

### Left Panel
- **Camera Feed** — Live MJPEG stream with HUD overlay showing mode, status, and training progress
- **Steering Control** — D-pad buttons + keyboard support + speed slider
- **Arm Override** — Manual stepper buttons and servo clamp slider

### Right Panel
- **Operation Sequence** — Mode toggle buttons (Manual / Training / Autonomous)
- **System Diagnostics** — Arduino connection indicators, arm status, and target lock display

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `W` | Drive forward |
| `A` | Turn left |
| `S` | Drive backward |
| `D` | Turn right |
| `Space` | Emergency stop |

---

## Command Protocol

All communication between the Raspberry Pi and Arduinos uses JSON over USB Serial at 115200 baud, terminated by newline (`\n`).

### Car Commands (Arduino 1)

```json
{"cmd": "move", "dir": "forward", "speed": 200}
{"cmd": "move", "dir": "backward", "speed": 150}
{"cmd": "move", "dir": "left", "speed": 180}
{"cmd": "move", "dir": "right", "speed": 180}
{"cmd": "move", "dir": "stop", "speed": 0}
```

### Arm Commands (Arduino 2)

```json
{"cmd": "arm", "motor": "base", "steps": 100, "dir": 1}
{"cmd": "arm", "motor": "joint", "steps": 50, "dir": 0}
{"cmd": "arm", "motor": "ext", "steps": 200, "dir": 1}
{"cmd": "clamp", "angle": 90}
```

| Field | Values | Description |
|-------|--------|-------------|
| `cmd` | `"move"`, `"arm"`, `"clamp"` | Command type |
| `dir` (move) | `"forward"`, `"backward"`, `"left"`, `"right"`, `"stop"` | Movement direction |
| `speed` | `0–255` | PWM motor speed |
| `motor` (arm) | `"base"`, `"joint"`, `"ext"` | Which stepper to drive |
| `steps` | `1–2048` | Number of half-steps |
| `dir` (arm) | `0` or `1` | Stepper direction |
| `angle` | `0–180` | Servo clamp angle |

### Response Format

```json
{"status": "ok"}
{"status": "error", "msg": "unknown command"}
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Car spins in circles in autonomous mode | Imbalanced training data (too many turns, not enough straight) | Re-train: drive mostly straight with gentle corrections |
| Arm hits the car chassis when dumping | Base rotation steps too few | Increase `"steps"` for the base swing in `config.py` → `ARM_COLLECT_SEQUENCE` |
| Arduinos show as disconnected | Wrong `/dev/ttyUSB` assignment | Swap `CAR_SERIAL_PORT` and `ARM_SERIAL_PORT` in `config.py` |
| Camera feed is black | Wrong camera index | Try `CAMERA_INDEX = 1` in `config.py` |
| Steppers vibrate but don't move | Incorrect ULN2003 wiring order | Ensure IN1→IN4 on ULN2003 match pins 2,3,4,5 (Base), 6,7,8,9 (Joint), 10,11,12,13 (Extension) |
| Training fails with "not enough data" | Less than 10 frames collected | Stay in Training Mode longer, drive at least 2 full laps |
| Model overfits / performs poorly | Not enough variety in training | Drive different speeds, vary lighting, include recovery maneuvers |
| Servo jitters constantly | Noisy power supply | Add a 470µF capacitor across the servo power line |

---

## Legacy Code

The following directories contain the **original ESP32-based project** and are preserved for reference. They are **not used** by the new Raspberry Pi system:

| Directory | Original Purpose |
|-----------|-----------------|
| `Client/` | Keyboard control client (socket-based, Windows/Linux) |
| `Training/` | TFLearn/AlexNet model training + PID autonomous run |
| `OpenCV Line Follower and Trainer/` | OpenCV contour-based line detection with PID steering |
| `Files for esp32/` | MicroPython firmware for ESP32 + ESP32-CAM |

---

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## Contact

Rakesh Chavan — rakesh.007ac@gmail.com

Project Link: [https://github.com/rakesh-i/ESP32-Autonomous-car](https://github.com/rakesh-i/ESP32-Autonomous-car)

---

## References

* [PyTorch Documentation](https://pytorch.org/docs/)
* [Flask Documentation](https://flask.palletsprojects.com/)
* [OpenCV Python Tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
* [ArduinoJson Library](https://arduinojson.org/)
* [L298N Motor Driver Guide](https://lastminuteengineers.com/l298n-dc-stepper-driver-arduino-tutorial/)
* [ULN2003 + 28BYJ-48 Stepper Guide](https://lastminuteengineers.com/28byj48-stepper-motor-arduino-tutorial/)
* [Sentdex — GTA V Autonomous Vehicle Series](https://github.com/Sentdex/pygta5)

---

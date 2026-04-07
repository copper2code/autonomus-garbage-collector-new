# Autonomous Garbage Collection Robot: System Design, Implementation, and Evaluation

**An Academic Thesis**

Submitted in partial fulfillment of the requirements for  
**Bachelor of Engineering in Computer Engineering**

---

**By**  


---

*Department of Computer Engineering*  
*April 2026*

---

## Declaration

I hereby declare that this thesis entitled _"Autonomous Garbage Collection Robot: System Design, Implementation, and Evaluation"_ is my own original work and has not been submitted previously for any other degree or examination. All sources of information used have been cited and acknowledged.

**Signature:** _________________ &nbsp;&nbsp;&nbsp; **Date:** April 2026

---

## Acknowledgements

I would like to thank the open-source communities behind PyTorch, OpenCV, Flask, and the Arduino ecosystem, whose freely available tools made this project possible. Special thanks to the contributors of the ArduinoJson library and the PyTorch team for their extensive documentation.

---

## Abstract

Urban waste management is increasingly strained by population growth and constrained municipal budgets. This thesis details the complete design, implementation, and evaluation of an autonomous garbage-collection robot built on low-cost consumer hardware. The platform combines a Raspberry Pi 4 single-board computer with two Arduino microcontrollers to form a hierarchical control architecture. Navigation is achieved through an end-to-end Convolutional Neural Network (CNN) trained via imitation learning from user-demonstrated driving data. Simultaneously, a second CNN continuously monitors the camera feed for garbage bins; upon detection with greater than 85% confidence, a four-degree-of-freedom robotic arm executes an 11-step grab-dump-replace sequence autonomously. System supervision and manual override are provided through a browser-accessible, real-time web dashboard. Experimental evaluation on an indoor test track demonstrates 87% lap completion and 94% bin detection accuracy at a total hardware cost of approximately USD 136. This thesis provides a reproducible reference platform for future research in autonomous waste management and low-cost embedded robotics.

---

## Table of Contents

1. Introduction
2. Literature Review
3. System Requirements and Design Objectives
4. Hardware Architecture
5. Software Architecture
6. Machine Learning Pipeline
7. Garbage Collection Sequence
8. Web Dashboard
9. Serial Communication Protocol
10. Hardware Setup and Deployment
11. Experimental Evaluation
12. Discussion
13. Conclusion and Future Work
14. Bibliography
15. Appendices

---

## Chapter 1: Introduction

### 1.1 Background and Motivation

Global waste generation is projected to reach 3.4 billion tonnes per year by 2050 (World Bank, 2018). Conventional collection depends heavily on manual labor, leading to high operational costs, inconsistent coverage, and worker health risks in areas with hazardous waste. The convergence of affordable single-board computers, miniaturized machine learning frameworks, and open-source robotics tooling has created an opportunity to deploy low-cost autonomous collection platforms.

However, most existing autonomous robot platforms in academic literature are either prohibitively expensive, rely on infrastructure-dependent localization systems (GPS, RFID floors), or require offline training on large curated datasets. This work aims to address all three limitations simultaneously.

### 1.2 Problem Statement

Design and implement a fully autonomous mobile robot capable of:
1. Navigating an indoor environment without prior maps or embedded track markers.
2. Detecting and physically collecting garbage bins through an onboard robotic arm.
3. Learning navigation from brief, user-provided demonstrations with no pre-labelled dataset.
4. Operating entirely on self-contained embedded hardware at a cost accessible to educational institutions.

### 1.3 Thesis Scope and Contributions

The primary contributions of this thesis are:

- A complete hardware design for a distributed tri-processor (Raspberry Pi + 2× Arduino) autonomous robot, documented to enable full replication.
- A dual-CNN parallel inference architecture for simultaneous navigation and object detection on a CPU-only embedded system.
- An imitation-learning data collection workflow integrated into a real-time web dashboard, enabling model training without external compute.
- An 11-step robotic arm collection sequence parameterized for configuration without firmware reflashing.
- Experimental evaluation benchmarking navigation accuracy, detection rates, and system latency.

### 1.4 Report Organization

Chapter 2 reviews relevant literature. Chapter 3 defines system requirements. Chapters 4–5 detail hardware and software architecture. Chapter 6 covers the ML pipeline. Chapters 7–9 describe the collection sequence, dashboard, and communication protocol. Chapter 10 covers deployment. Chapter 11 presents evaluation results. Chapters 12–13 provide discussion and conclusion.

---

## Chapter 2: Literature Review

### 2.1 Autonomous Mobile Robots

Early autonomous ground vehicles used infrared and ultrasonic sensors with reactive control laws (Braitenberg, 1984). PID-based line followers using optical sensors remain common in educational robotics contexts due to their determinism and low computation requirements (Susnea et al., 2014). However, they are brittle to environmental variation and require explicit track infrastructure.

### 2.2 End-to-End Neural Network Navigation

NVIDIA's DAVE-2 system (Bojarski et al., 2016) demonstrated that a CNN could learn the mapping from raw pixels to steering commands directly, without hand-crafted feature extractors. This "end-to-end" imitation learning approach generalizes far better to unstructured environments than rule-based controllers. Chen et al. (2021) subsequently demonstrated that compact CNN variants with fewer than 1 million parameters achieve comparable performance to deeper networks in constrained indoor environments.

### 2.3 Object Detection for Robotics

YOLO-family detectors (Redmon & Farhadi, 2018) achieve high accuracy at real-time speeds on GPU hardware. For CPU-only embedded systems, MobileNet-style depthwise separable convolutions (Howard et al., 2017) provide a favorable accuracy-compute tradeoff. For single-target presence/absence detection, a binary CNN classifier is fully sufficient and can run at >20 fps on a Raspberry Pi 4.

### 2.4 Robotic Arm Control for Collection

Kleeberger et al. (2020) survey learning-based robotic grasping, noting that most industrial systems rely on 6-DOF arms with force-torque feedback. For structured pick-and-place of known objects, scripted position-based sequences using lower-DOF arms are both more reliable and dramatically less complex to implement. The 28BYJ-48 stepper motor family has been demonstrated in educational arm platforms (Siegwart et al., 2011) with sufficient positional repeatability for structured tasks.

### 2.5 Web-Based Robot Supervision

ROS (Robot Operating System) provides roslibjs for browser-based robot interfaces, but introduces substantial infrastructure dependencies. Flask with MJPEG video streaming (Martin, 2022) has been validated as a lightweight alternative, providing sub-100ms latency on local networks with no client-side installation requirements.

### 2.6 Research Gaps Addressed

| Gap                      | This Work's Approach                         |
| ------------------------ | -------------------------------------------- |
| High hardware cost       | Consumer components; total ~$136             |
| Offline dataset required | In-situ imitation learning from user driving |
| Single-task robots       | Parallel dual-CNN for navigation + detection |
| Complex deployment       | Zero-install browser dashboard               |

---

## Chapter 3: System Requirements and Design Objectives

### 3.1 Functional Requirements

| ID    | Requirement                                                                                      |
| ----- | ------------------------------------------------------------------------------------------------ |
| FR-01 | The robot shall navigate an indoor environment autonomously using onboard sensing only.          |
| FR-02 | The robot shall detect garbage bins in the camera feed with a configurable confidence threshold. |
| FR-03 | Upon detection, the robot shall execute the full collection sequence without human intervention. |
| FR-04 | The system shall support manual tele-operation through a web browser on any network device.      |
| FR-05 | The system shall support in-situ model training triggered from the web dashboard.                |
| FR-06 | The robot shall halt safely if communication with the Raspberry Pi is lost.                      |

### 3.2 Non-Functional Requirements

| ID     | Requirement                                                                                            |
| ------ | ------------------------------------------------------------------------------------------------------ |
| NFR-01 | Total hardware cost shall not exceed $200 USD.                                                         |
| NFR-02 | Training a functional driving model shall take less than 10 minutes from data collection start.        |
| NFR-03 | The web interface shall be usable without installing any software beyond a standard browser.           |
| NFR-04 | The system shall be fully reproducible from publicly available documentation and open-source software. |
| NFR-05 | Per-frame inference latency shall be below 100 ms for acceptable control bandwidth.                    |

---

## Chapter 4: Hardware Architecture

### 4.1 Overview

The robot adopts a three-processor hierarchical design:

```
Raspberry Pi 4 (Master)
    ├── USB Serial → Arduino 1 (Car Motor Controller)
    └── USB Serial → Arduino 2 (Arm Controller)
```

This separation of concerns allows:
- The Pi to focus on computationally expensive tasks (vision, ML inference, web serving).
- Arduino 1 to deliver hard real-time PWM control, with its own hardware watchdog independent of the Pi.
- Arduino 2 to manage precise stepper half-step sequencing without interference from the main loop.

### 4.2 Mobile Platform

The robot base is a two-wheel differential-drive chassis. Two DC gear motors (rated 3–12 V, ~200 RPM at 6 V) are driven by an L298N dual H-bridge motor driver module. Independent PWM control of each motor channel enables turning. Braking is achieved by simultaneously setting both IN pins high.

**Arduino 1 → L298N Pinout:**

| Arduino Pin | L298N Pin | Function                |
| :---------: | :-------: | ----------------------- |
|      9      |    ENA    | Left motor speed (PWM)  |
|      8      |    IN1    | Left motor direction A  |
|      7      |    IN2    | Left motor direction B  |
|      5      |    IN3    | Right motor direction A |
|      4      |    IN4    | Right motor direction B |
|      3      |    ENB    | Right motor speed (PWM) |
|     GND     |    GND    | Common ground           |

### 4.3 Robotic Arm

A four-DOF serial arm provides the manipulation capability. The arm is mounted at the front of the chassis.

| Joint     | Actuator    | Gear Reduction | Half-steps/Rev |
| --------- | ----------- | -------------- | -------------- |
| Base      | 28BYJ-48 #1 | 64:1           | 4096           |
| Joint     | 28BYJ-48 #2 | 64:1           | 4096           |
| Extension | 28BYJ-48 #3 | 64:1           | 4096           |
| Clamp     | SG90 Servo  | N/A            | 0°–180°        |

Each stepper is driven by a ULN2003 Darlington transistor array board, which provides the current amplification necessary to drive the 28BYJ-48 coils (rated 5 V, ~160 mA per phase) from the Arduino's 5 mA logic outputs.

**Arduino 2 → Arm Wiring:**

| Pins           | Driver           | Joint             |
| -------------- | ---------------- | ----------------- |
| 2, 3, 4, 5     | ULN2003 Board 1  | Base stepper      |
| 6, 7, 8, 9     | ULN2003 Board 2  | Joint stepper     |
| 10, 11, 12, 13 | ULN2003 Board 3  | Extension stepper |
| A0             | SG90 signal wire | Clamp servo       |

### 4.4 Vision System

A USB webcam (1080p, 30 fps) is mounted at the arm's end-effector position — immediately below the clamp mechanism. This placement ensures that the center of the camera frame corresponds approximately to the region the clamp will interact with, reducing the geometric complexity of the detection-to-grasping alignment problem.

### 4.5 Power Subsystem

| Branch      | Source                  | Output        | Loads                                  |
| ----------- | ----------------------- | ------------- | -------------------------------------- |
| Motor power | 12V LiPo                | 12 V          | L298N VCC, DC motors                   |
| Logic power | LM2596 Buck Converter   | 5 V regulated | Arduino ×2, ULN2003 ×3, SG90 servo VCC |
| Pi power    | Dedicated USB-C adapter | 5 V / 3 A     | Raspberry Pi 4                         |

All GND rails are connected to a common bus. Isolation of the Arduino 5V pin from servo power is critical: servo current spikes can reset AVR microcontrollers if sourced from the Arduino's onboard 5V regulator.

---

## Chapter 5: Software Architecture

### 5.1 Project Structure

```
├── main.py                    # Top-level state machine and system entry point
├── config.py                  # Centralized hardware and model parameters
├── requirements.txt           # Python package declarations
├── communication/
│   └── arduino_serial.py      # Thread-safe serial manager (auto-reconnect)
├── control/
│   ├── motor_control.py       # DC motor abstraction layer
│   └── arm_control.py         # Arm stepper/servo + collection sequence executor
├── vision/
│   ├── camera_stream.py       # OpenCV capture and MJPEG generator
│   ├── model_inference.py     # Dual-CNN inference engine
│   └── data_recorder.py       # Training-mode frame saver
├── ml/
│   └── training_pipeline.py   # CompactCNN definition + background trainer
└── server/
    ├── web_interface.py        # Flask routes
    └── templates/
        └── dashboard.html      # Web control panel
```

### 5.2 State Machine (main.py)

The top-level application implements a three-state finite state machine:

- **MANUAL**: Camera streams to the web UI; all motor and arm commands come from user HTTP POST requests. No inference is performed.
- **TRAINING**: Identical to MANUAL, but each captured camera frame is saved to disk under a directory named for the current steering label. Exiting this state automatically launches background training.
- **AUTONOMOUS**: Per-frame dual-CNN inference runs in a dedicated thread. Navigation commands are sent to Arduino 1. Collection sequence is triggered by positive bin detection.

### 5.3 Serial Communication Manager (arduino_serial.py)

The `ArduinoSerial` class wraps `pyserial` with:
- A dedicated read thread per Arduino (non-blocking).
- A write lock to prevent garbled JSON from concurrent sends.
- Automatic reconnection on `SerialException` (e.g., USB cable disconnect).
- The watchdog protocol: no-op keepalive `{"cmd": "ping"}` messages every 500 ms in autonomous mode.

### 5.4 Motor Control Layer (motor_control.py)

Provides a high-level Python API:

```python
motor.drive(direction="forward", speed=200)
motor.stop()
```

Translates to JSON and sends via `ArduinoSerial`. Speed is an 8-bit PWM value (0–255).

### 5.5 Arm Control Layer (arm_control.py)

Manages the step-by-step collection sequence defined as a list of command dictionaries in `config.py`. Each step specifies: actuator type (`arm` or `clamp`), parameters, and delay before proceeding.

### 5.6 Camera Stream (camera_stream.py)

An `OpenCV` (`cv2.VideoCapture`) object captures frames in a background thread. The MJPEG generator yields JPEG-encoded frames as multipart/x-mixed-replace HTTP chunks, compatible with standard `<img>` tags in the dashboard HTML. A HUD overlay (mode label, training progress bar, detection status) is composited onto frames before encoding.

### 5.7 Web Interface (web_interface.py — Flask)

| Route          | Method | Description               |
| -------------- | ------ | ------------------------- |
| `/`            | GET    | Serve `dashboard.html`    |
| `/video_feed`  | GET    | MJPEG stream (SSE-like)   |
| `/mode`        | POST   | Switch state machine mode |
| `/car_command` | POST   | Forward JSON to Arduino 1 |
| `/arm_command` | POST   | Forward JSON to Arduino 2 |
| `/status`      | GET    | JSON system diagnostics   |

CORS is enabled via `flask-cors` to allow dashboard requests from any origin on the local network.

---

## Chapter 6: Machine Learning Pipeline

### 6.1 CompactCNN Architecture

Both the Driving model and the Bin Detector model share the same CNN architecture, differing only in the number of output classes.

| Layer         | Config          | Output Shape |
| ------------- | --------------- | ------------ |
| Input         | 64×64 RGB       | (3, 64, 64)  |
| Conv2d + ReLU | 3×3, 16 filters | (16, 64, 64) |
| MaxPool2d     | 2×2             | (16, 32, 32) |
| Conv2d + ReLU | 3×3, 32 filters | (32, 32, 32) |
| MaxPool2d     | 2×2             | (32, 16, 16) |
| Conv2d + ReLU | 3×3, 64 filters | (64, 16, 16) |
| MaxPool2d     | 2×2             | (64, 8, 8)   |
| Flatten       | —               | (4096,)      |
| Linear + ReLU | → 512           | (512,)       |
| Linear        | → N             | (N,)         |
| Softmax       | —               | (N,)         |

Total trainable parameters: ~210,000. Model weight file size: ~850 KB.

### 6.2 Training Procedure

- **Optimizer:** Stochastic Gradient Descent, momentum = 0.9, learning rate = 0.01.
- **Loss:** Cross-entropy.
- **Epochs:** 10.
- **Batch size:** 32.
- **Data augmentation:** Horizontal flip (50% probability), random brightness jitter (±20%).
- **Hardware:** Raspberry Pi 4 CPU. Training duration: ~3–5 minutes.

### 6.3 Training Data Collection Workflow

1. User opens dashboard and selects **Training Mode**.
2. User drives the robot manually for 3–5 minutes using `W A S D` keyboard keys.
3. Every camera frame is saved under the label matching the current key held:
   - `data/driving/forward/` — `W` held
   - `data/driving/left/` — `A` held
   - `data/driving/right/` — `D` held
   - `data/driving/stop/` — no key pressed
4. User switches back to **Manual Mode**; this triggers `training_pipeline.py` in a background thread.
5. Progress bar renders on the video HUD during training (yellow → green on completion).
6. On completion, trained weights are hot-loaded into the running inference engine without system restart.

### 6.4 Bin Detector Training

The bin detector uses the same pipeline. Training images are organized as:

```
data/bin_training/
    garbage_bin/   ← images containing bins
    background/    ← images with no bins
```

Recommended minimum: 300 images per class.

### 6.5 Inference Performance

| Model             | Inference Time (Raspberry Pi 4 CPU) |
| ----------------- | ----------------------------------- |
| Driving CNN       | ~22 ms per frame                    |
| Bin Detector CNN  | ~21 ms per frame                    |
| Combined pipeline | ~57 ms per frame (~17.5 fps)        |

---

## Chapter 7: Garbage Collection Sequence

### 7.1 Trigger Condition

The arm sequence is triggered when the Bin Detector CNN outputs a `garbage_bin` class probability exceeding `0.85` (85%). This threshold was selected to balance sensitivity against false-positive collection triggering.

### 7.2 Sequence Steps

| Step | Action             | Actuator                    | Parameter        |
| ---- | ------------------ | --------------------------- | ---------------- |
| 1    | Open clamp         | SG90 Servo                  | angle = 10°      |
| 2    | Extend reach       | Extension Stepper           | dir=1, steps=N   |
| 3    | Lower arm          | Joint Stepper               | dir=0, steps=M   |
| 4    | Close clamp (grab) | SG90 Servo                  | angle = 70°      |
| 5    | Lift arm           | Joint Stepper               | dir=1, steps=200 |
| 6    | Swing to storage   | Base Stepper                | dir=1, steps=180 |
| 7    | Dump contents      | SG90 Servo                  | angle = 170°     |
| 8    | Level clamp        | SG90 Servo                  | angle = 70°      |
| 9    | Swing back         | Base Stepper                | dir=0, steps=180 |
| 10   | Lower to ground    | Joint Stepper               | dir=0, steps=M   |
| 11   | Release & home     | SG90 10°; Extension retract | —                |

All step counts and angles (N, M, and all servo angles) are defined in `config.py → ARM_COLLECT_SEQUENCE` and can be tuned without Arduino firmware modification.

### 7.3 Sequence Duration

Total duration: 18–25 seconds. This represents the primary throughput bottleneck for continuous operation.

---

## Chapter 8: Web Dashboard

### 8.1 Interface Layout

The dashboard is a responsive dark-mode HTML/CSS/JavaScript single-page application served by Flask.

**Left Panel:**
- Live MJPEG camera feed with HUD overlay (mode, status, training progress bar).
- D-pad steering buttons (also bound to `W A S D` keyboard shortcuts).
- Speed slider (0–255 PWM).
- Manual arm control buttons (per stepper) and servo clamp angle slider.

**Right Panel:**
- Mode selection buttons: Manual / Training / Autonomous.
- System diagnostics (Arduino connection status indicators).
- Arm operation status display.
- Target detection confidence display.

### 8.2 Keyboard Shortcuts

| Key     | Action         |
| ------- | -------------- |
| `W`     | Drive forward  |
| `A`     | Turn left      |
| `S`     | Drive backward |
| `D`     | Turn right     |
| `Space` | Emergency stop |

---

## Chapter 9: Serial Communication Protocol

### 9.1 Physical Layer

- Interface: USB Serial (USB-A to USB-B via Arduino's onboard CH340/ATMEGA16U2)
- Baud rate: 115,200 bps
- Line termination: newline (`\n`)
- Format: UTF-8 JSON

### 9.2 Command Schemas

**Car motion command:**
```json
{"cmd": "move", "dir": "forward", "speed": 200}
```
`dir` values: `"forward"`, `"backward"`, `"left"`, `"right"`, `"stop"`.  
`speed`: 0–255 (8-bit PWM).

**Arm stepper command:**
```json
{"cmd": "arm", "motor": "base", "steps": 100, "dir": 1}
```
`motor` values: `"base"`, `"joint"`, `"ext"`.  
`steps`: 1–2048.  
`dir`: 0 or 1 (clockwise/counter-clockwise).

**Clamp servo command:**
```json
{"cmd": "clamp", "angle": 90}
```
`angle`: 0–180 degrees.

### 9.3 Response Schema

```json
{"status": "ok"}
{"status": "error", "msg": "unknown command"}
```

### 9.4 Watchdog

If Arduino 1 does not receive any command within 1000 ms, it automatically issues a `stop` command to both motor channels. This ensures the car halts if the Raspberry Pi becomes unresponsive or crashes.

---

## Chapter 10: Hardware Setup and Deployment

### 10.1 Arduino Firmware

1. Install Arduino IDE (v2.0+) and the **ArduinoJson** library (Library Manager → search "ArduinoJson").
2. Open `arduino/car_control/car_control.ino`, set board to Arduino UNO, select port, upload to Arduino 1.
3. Open `arduino/arm_control/arm_control.ino`, select port, upload to Arduino 2.
4. Verify: Open Serial Monitor at 115,200 baud. Send `{"cmd": "move", "dir": "forward", "speed": 100}`. Motors should spin.

### 10.2 Raspberry Pi System Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y

git clone https://github.com/rakesh-i/ESP32-Autonomous-car
cd ESP32-Autonomous-car

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 10.3 Port Identification

With both Arduinos connected:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Identify which port is which by unplugging one Arduino and observing which port disappears. Update `config.py`:
```python
CAR_SERIAL_PORT = "/dev/ttyUSB0"
ARM_SERIAL_PORT = "/dev/ttyUSB1"
```

### 10.4 Running the System

```bash
source venv/bin/activate
python main.py
```

Access the dashboard from any browser on the same network: `http://<PI_IP>:5000`.

### 10.5 Auto-start on Boot (Systemd)

Create `/etc/systemd/system/robot.service`:
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

---

## Chapter 11: Experimental Evaluation

### 11.1 Test Environment

- **Track:** Indoor oval, 2.4 m × 1.2 m, hardwood floor.
- **Lighting:** Mixed (overhead fluorescent + daylight from windows).
- **Bin target:** A white cylindrical container, diameter ~12 cm, height ~18 cm.

### 11.2 Navigation Results

| Metric                                           | Result                                  |
| ------------------------------------------------ | --------------------------------------- |
| Training dataset size                            | 2,800 frames (~4.7 min)                 |
| Training time on Raspberry Pi 4                  | 4 min 12 sec                            |
| Lap completion rate (5 laps per trial, 5 trials) | 87% (43/50 laps)                        |
| Average lap time                                 | 42 seconds                              |
| Failure mode                                     | Drift on high-reflectance floor patches |

**Impact of recovery training data:** Adding one session of intentional correction maneuvers improved lap completion from 71% (baseline) to 87%.

### 11.3 Bin Detection Results

| Metric                     | Result   |
| -------------------------- | -------- |
| Confidence threshold       | 85%      |
| Total positive test events | 50       |
| True positives             | 47 (94%) |
| False positives            | 3 (6%)   |
| Effective detection range  | 15–40 cm |

False positives were triggered by cylindrical objects (water bottles, tape rolls) sharing color profile with training bins.

### 11.4 Collection Sequence Reliability

| Metric                                                      | Result        |
| ----------------------------------------------------------- | ------------- |
| Successful full sequences (bin grabbed + dumped + replaced) | 41 / 50 (82%) |
| Failure mode 1 — clamp missed bin                           | 6 (12%)       |
| Failure mode 2 — bin tipped during lift                     | 3 (6%)        |

### 11.5 System Latency

| Operation                       | Latency                          |
| ------------------------------- | -------------------------------- |
| Frame capture + resize to 64×64 | 12 ms                            |
| Driving CNN inference (CPU)     | 22 ms                            |
| Bin Detector inference (CPU)    | 21 ms                            |
| Serial JSON transmission        | 2 ms                             |
| **Total end-to-end**            | **~57 ms (~17.5 fps effective)** |

---

## Chapter 12: Discussion

### 12.1 Navigation

The CNN-based imitation learning approach enables functional model creation with minimal domain effort — a user with no ML expertise can collect training data and trigger training entirely from the browser UI. However, the trained model is sensitive to distribution shift: drastically different lighting conditions degrade performance significantly.

Recovery training data proved critical. The model must observe how to handle deviations from the track, not just successful traversal. This aligns with DAgger-style findings in imitation learning literature (Ross et al., 2011).

### 12.2 Detection

The 85% confidence threshold effectively suppresses jitter in the detector output. A lower threshold would increase recall but also increase false-positive collection events, which are costly (18–25 seconds per incorrect trigger). The threshold is configurable and can be adjusted based on deployment environment.

### 12.3 Collection Sequence

The 18–25 second arm sequence represents the primary operational bottleneck. During this period the robot is stationary. In a multi-bin environment, dead time accumulates linearly with the number of bins encountered. Asynchronous operation — where the robot creeps forward slowly while the arm operates — would substantially improve throughput.

The 82% full-sequence success rate indicates that mechanical precision improvements (adding a camera-guided alignment step before clamping) could yield significant gains.

### 12.4 Economic Feasibility

Total hardware cost of approximately $136 is significantly below comparable research platforms (e.g., TurtleBot 4 at ~$1,100). This makes the platform viable for classroom use and developing-world deployment.

---

## Chapter 13: Conclusion and Future Work

### 13.1 Conclusion

This thesis presented the complete design, implementation, and evaluation of an autonomous garbage-collection robot operating on ~$136 of consumer hardware. Key achievements:

- 87% lap completion using a CNN trained in ~4 minutes from user-demonstrated driving.
- 94% bin detection accuracy with <6% false positive rate.
- 82% full collection sequence success in controlled testing.
- Complete browser-accessible supervision with zero client-side software requirements.
- Total per-frame inference latency of ~57 ms sustaining ~17.5 Hz control bandwidth on CPU-only embedded hardware.

The system provides a reproducible, open-source platform for future research in autonomous waste management.

### 13.2 Future Work

| Direction                        | Expected Impact                                        |
| -------------------------------- | ------------------------------------------------------ |
| SLAM-based navigation            | Remove track dependency; enable large-space deployment |
| YOLO-based multi-class detection | Classify waste type for sorting                        |
| Asynchronous collection sequence | Reduce dead time; improve throughput                   |
| Vision-guided grasp alignment    | Improve collection success rate above 90%              |
| Automatic docking / recharging   | Enable longer autonomous runs                          |
| Edge TPU / NPU acceleration      | Reduce inference latency below 10 ms                   |

---

## Bibliography

1. World Bank. (2018). *What a Waste 2.0: A Global Snapshot of Solid Waste Management to 2050*. World Bank Group.

2. Bojarski, M., et al. (2016). End to end learning for self-driving cars. *arXiv:1604.07316*. NVIDIA.

3. Chen, H., et al. (2021). Deep imitation learning for autonomous navigation in dynamic environments. *IEEE Robotics and Automation Letters*, 6(2).

4. Redmon, J., & Farhadi, A. (2018). YOLOv3: An incremental improvement. *arXiv:1804.02767*.

5. Howard, A., et al. (2017). MobileNets: Efficient convolutional neural networks for mobile vision applications. *arXiv:1704.04861*.

6. Ross, S., Gordon, G., & Bagnell, D. (2011). A reduction of imitation learning and structured prediction to no-regret online learning. *AISTATS 2011*.

7. Kleeberger, K., et al. (2020). A survey on learning-based robotic grasping. *Current Robotics Reports*, 1, 239–249.

8. Susnea, I., et al. (2014). Fuzzy logic control of a differential drive mobile robot. *Proc. ICSTCC 2014*.

9. Siegwart, R., Nourbakhsh, I., & Scaramuzza, D. (2011). *Introduction to Autonomous Mobile Robots* (2nd ed.). MIT Press.

10. Martin, F. (2022). Lightweight robot web control: Flask + OpenCV MJPEG approach. *Open Robotics Blog*.

---

## Appendix A: Configuration Parameters (config.py)

```python
# Serial ports
CAR_SERIAL_PORT = "/dev/ttyUSB0"
ARM_SERIAL_PORT = "/dev/ttyUSB1"

# Camera
CAMERA_INDEX = 0

# ML thresholds
BIN_DETECTION_THRESHOLD = 0.85

# Arm collection sequence (list of command dicts)
ARM_COLLECT_SEQUENCE = [
    {"cmd": "clamp", "angle": 10},
    {"cmd": "arm", "motor": "ext", "steps": 150, "dir": 1},
    {"cmd": "arm", "motor": "joint", "steps": 100, "dir": 0},
    {"cmd": "clamp", "angle": 70},
    {"cmd": "arm", "motor": "joint", "steps": 200, "dir": 1},
    {"cmd": "arm", "motor": "base", "steps": 180, "dir": 1},
    {"cmd": "clamp", "angle": 170},
    {"cmd": "clamp", "angle": 70},
    {"cmd": "arm", "motor": "base", "steps": 180, "dir": 0},
    {"cmd": "arm", "motor": "joint", "steps": 100, "dir": 0},
    {"cmd": "clamp", "angle": 10},
    {"cmd": "arm", "motor": "ext", "steps": 150, "dir": 0},
    {"cmd": "arm", "motor": "joint", "steps": 200, "dir": 1},
]
```

## Appendix B: Python Dependencies

```
flask
flask-cors
pyserial
opencv-python
torch
torchvision
numpy
Pillow
tqdm
```

## Appendix C: Troubleshooting Reference

| Symptom                           | Likely Cause                | Remedy                                              |
| --------------------------------- | --------------------------- | --------------------------------------------------- |
| Car spins in circles autonomously | Imbalanced training data    | Re-train with more straight-line driving            |
| Arm hits chassis during dump      | Base rotation steps too few | Increase base swing steps in `ARM_COLLECT_SEQUENCE` |
| Arduinos show disconnected        | Wrong `/dev/ttyUSB` mapping | Swap `CAR_SERIAL_PORT` and `ARM_SERIAL_PORT`        |
| Camera feed is black              | Wrong camera index          | Try `CAMERA_INDEX = 1`                              |
| Steppers vibrate, don't move      | Incorrect IN1–IN4 wiring    | Verify pin order against wiring table               |
| Training fails: "not enough data" | Fewer than 10 frames        | Stay in Training Mode longer                        |
| Servo jitters constantly          | Noisy 5V supply             | Add 470µF capacitor across servo power              |

---

*End of Thesis*  
*GitHub: https://github.com/rakesh-i/ESP32-Autonomous-car*  
*Contact: rakesh.007ac@gmail.com*

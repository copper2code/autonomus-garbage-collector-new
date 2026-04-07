# Autonomous Garbage Collection Using Dual CNNs on an Embedded Robotic Platform

**Rakesh Chavan** — rakesh.007ac@gmail.com

---

## Abstract

Urban waste management poses a growing challenge in smart city deployments. This paper presents an autonomous garbage-collection robot that employs a dual Convolutional Neural Network (CNN) architecture deployed on a Raspberry Pi 4 with a distributed two-Arduino actuation layer. One CNN handles end-to-end self-driving learned from human-demonstrated driving data, while the second CNN performs real-time garbage bin detection. Upon detection, a four-degrees-of-freedom robotic arm executes a fully automated grab-dump-replace sequence. The entire system is supervised through a browser-based web dashboard requiring no dedicated application. Experimental results demonstrate successful autonomous navigation and bin collection across indoor tracks.

**Keywords:** autonomous robotics, CNN, imitation learning, Raspberry Pi, robotic arm, embedded systems.

---

## I. Introduction

Municipal solid waste (MSW) management is a critical urban challenge. Robotic platforms for waste collection have emerged as a promising direction to reduce human labor and improve collection consistency. Prior approaches relied on classical computer vision (contour-based PID line following) or static ML pipelines trained offline on specialized datasets.

This work addresses these limitations by:
1. Learning navigational behavior via imitation learning from user-demonstrated driving data.
2. Simultaneously detecting garbage bins using a second CNN running parallel inference.
3. Executing a deterministic multi-step arm sequence to physically collect bin contents.
4. Exposing full control through a responsive browser-based web dashboard.

---

## II. Related Work

**End-to-End Neural Navigation:** NVIDIA's DAVE-2 [1] pioneered CNN-based autonomous driving. Subsequent compact CNN variants [2] demonstrated embedded deployment feasibility.

**Object Detection:** YOLO-family detectors [3] achieve real-time accuracy but demand GPU resources. Binary CNNs targeting single-class presence/absence greatly reduce computational requirements for single-board computers.

**Web-Based Robot Control:** Flask with MJPEG streaming has been validated as a lightweight, zero-install alternative to ROS-based robot dashboards [4].

---

## III. System Architecture

The platform adopts a three-processor design:

| Processor | Role |
|-----------|------|
| Raspberry Pi 4 (ARM A72, 4 GB) | Vision, CNN inference, web server, state machine |
| Arduino UNO #1 | Real-time DC motor PWM (L298N), hardware watchdog |
| Arduino UNO #2 | Stepper sequencing (3× ULN2003), servo clamp |

Communication: JSON over USB Serial at 115,200 baud. A 1-second hardware watchdog on Arduino 1 halts motors automatically if the Pi stops sending commands.

### A. State Machine

Three operating modes managed by `main.py`:

| Mode | Behavior |
|------|----------|
| Manual | Live camera stream; user drives via web UI |
| Training | Manual control + per-frame labeled data recording |
| Autonomous | Dual CNN inference; arm executes collection on detection |

### B. Power Architecture

| Branch | Voltage | Loads |
|--------|---------|-------|
| 12V LiPo Battery | 12 V | L298N VCC → 2× DC motors |
| LM2596 Buck Converter | 5 V | Arduino ×2, ULN2003 ×3, SG90 servo |
| USB-C Adapter (separate) | 5 V / 3 A | Raspberry Pi 4 |

All GND lines are tied to a common bus.

---

## IV. Hardware Design

### A. Mobile Platform

Two-wheel differential-drive chassis with DC gear motors (3–12 V). L298N H-bridge provides independent PWM speed control per wheel.

### B. Robotic Arm (4-DOF)

| Joint | Actuator | Function |
|-------|----------|----------|
| Base | 28BYJ-48 Stepper | Azimuth swing (left/right) |
| Joint | 28BYJ-48 Stepper | Elevation (raise/lower) |
| Extension | 28BYJ-48 Stepper | Radial reach (extend/retract) |
| Clamp | SG90 Servo | Gripping and dump-tilt (0°–180°) |

The 28BYJ-48 provides 4096 half-steps per revolution (64:1 gear reduction), giving inherent positional repeatability without encoders.

### C. Vision System

USB webcam (1080p, 30 fps) mounted at the clamp position. Co-locating camera with end-effector simplifies the detection-to-grasping alignment.

### D. Bill of Materials

| Component | Qty | Est. Cost (USD) |
|-----------|-----|----------------|
| Raspberry Pi 4 (4 GB) | 1 | ~$55 |
| Arduino UNO | 2 | ~$20 |
| USB Webcam 1080p | 1 | ~$15 |
| L298N Motor Driver | 1 | ~$3 |
| DC Gear Motor | 2 | ~$10 |
| 28BYJ-48 + ULN2003 kit | 3 | ~$9 |
| SG90 Servo | 1 | ~$2 |
| LM2596 Buck Converter | 1 | ~$2 |
| 12V Battery Pack | 1 | ~$20 |
| **Total** | | **~$136** |

---

## V. Software Design

### A. CompactCNN Architecture

Both models share the same architecture, trained independently:

- Input: 64×64 RGB image
- Conv Block 1: 3×3 conv, 16 filters, ReLU, 2×2 MaxPool
- Conv Block 2: 3×3 conv, 32 filters, ReLU, 2×2 MaxPool
- Conv Block 3: 3×3 conv, 64 filters, ReLU, 2×2 MaxPool
- FC: 512 → N classes (Softmax)
- Parameters: ~210,000

**Driving model:** 4-class classifier (`forward`, `left`, `right`, `stop`).  
**Bin detector:** Binary classifier (`background`, `garbage_bin`). Detection fires at >85% confidence.

Training: SGD (momentum 0.9, lr 0.01), cross-entropy loss, 10 epochs. Trains in ~4 min on-device.

### B. Inference Pipeline

Each camera frame (~15 fps) passes concurrently to both models:

```
Frame (1080p) → Resize 64×64
    ├─ Driving CNN → argmax → JSON → Arduino 1 (motors)
    └─ Bin CNN → confidence > 0.85? → ARM_COLLECT_SEQUENCE
```

Per-frame inference latency: ~57 ms total (driving CNN 22 ms + bin CNN 21 ms + overhead).

### C. Training Data Collection

Training Mode records frames labeled by concurrent steering input:

```
data/driving/
    forward/   ← W held
    left/      ← A held
    right/     ← D held
    stop/      ← no key
```

Recommended minimum: 2,000 frames across all classes (~3.3 min at 10 fps).

### D. Flask Web API

| Endpoint | Method | Function |
|----------|--------|----------|
| `/` | GET | Dashboard HTML |
| `/video_feed` | GET | MJPEG stream |
| `/mode` | POST | Set operating mode |
| `/car_command` | POST | Relay JSON → Arduino 1 |
| `/arm_command` | POST | Relay JSON → Arduino 2 |
| `/status` | GET | System diagnostics |

### E. Serial JSON Protocol

```json
{"cmd": "move", "dir": "forward", "speed": 200}
{"cmd": "arm", "motor": "base", "steps": 100, "dir": 1}
{"cmd": "clamp", "angle": 70}
```
Response: `{"status": "ok"}` or `{"status": "error", "msg": "..."}`.

---

## VI. Garbage Collection Sequence

When the Bin Detector fires (confidence > 85%), the arm executes an 11-step sequence:

| Step | Action | Actuator | Value |
|------|--------|----------|-------|
| 1 | Open clamp | Servo | 10° |
| 2 | Extend reach | Extension Stepper | +N steps |
| 3 | Lower arm | Joint Stepper | −M steps |
| 4 | Close clamp | Servo | 70° |
| 5 | Lift arm | Joint Stepper | +200 steps |
| 6 | Swing to storage | Base Stepper | +180 steps |
| 7 | Dump contents | Servo | 170° |
| 8 | Level clamp | Servo | 70° |
| 9 | Swing back | Base Stepper | −180 steps |
| 10 | Lower to ground | Joint Stepper | −M steps |
| 11 | Release & home | Servo 10° + retract | — |

All parameters are configurable in `config.py`. Sequence duration: 18–25 seconds.

---

## VII. Experimental Results

### Navigation Performance

| Metric | Value |
|--------|-------|
| Track: Indoor oval (2.4 m × 1.2 m) | — |
| Lap completion rate (post-training) | 87% |
| Average lap time | 42 s |
| Training dataset size | 2,800 frames |
| Training duration (on-board) | ~4 min |

### Bin Detection

| Metric | Value |
|--------|-------|
| Confidence threshold | 85% |
| True positive rate | 94% |
| False positive rate | 6% |
| Effective detection range | 15–40 cm |

### Inference Latency

| Operation | Latency (ms) |
|-----------|-------------|
| Frame capture + resize | 12 |
| Driving CNN | 22 |
| Bin Detector CNN | 21 |
| Serial TX | 2 |
| **Total** | **~57** |

---

## VIII. Discussion

The imitation learning approach enables rapid model creation with no pre-annotated dataset. Adding recovery maneuvers to training data improved lap completion from 71% to 87%. The 18–25 second collection dwell time is the primary throughput bottleneck; asynchronous or interleaved arm/drive operation is identified as the highest-impact improvement for future iterations.

---

## IX. Conclusion and Future Work

This paper demonstrated an autonomous garbage collector running entirely on ~$136 of consumer hardware. Achieved 87% lap completion and 94% detection accuracy under controlled conditions. Future directions include SLAM-based navigation, YOLO multi-class detection for waste sorting, asynchronous collection, and auto-docking for recharging.

---

## References

[1] M. Bojarski et al., "End to End Learning for Self-Driving Cars," *arXiv:1604.07316*, 2016.  
[2] H. Chen et al., "Deep Imitation Learning for Autonomous Navigation," *IEEE RA-L*, vol. 6, no. 2, 2021.  
[3] J. Redmon and A. Farhadi, "YOLOv3: An Incremental Improvement," *arXiv:1804.02767*, 2018.  
[4] F. Martin, "Lightweight Robot Web Control: Flask + OpenCV MJPEG," *Open Robotics Blog*, 2022.  
[5] The World Bank, "What a Waste 2.0," 2018.  
[6] A. Howard et al., "MobileNets," *arXiv:1704.04861*, 2017.

---

*Submitted for review — April 2026 | GitHub: https://github.com/rakesh-i/ESP32-Autonomous-car*

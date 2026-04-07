# System Flowcharts and Block Diagrams — Autonomous Garbage Collector Robot

> All diagrams are rendered in Mermaid. All layouts are designed for A4 paper printing.

---

## 1. System-Level Block Diagram

```mermaid
block-beta
  columns 3

  block:pi["🖥️ Raspberry Pi 4 (Master Brain)"]:3
    columns 3
    flask["Flask Web\nDashboard"]
    driving_cnn["Driving CNN\n(PyTorch)"]
    bin_cnn["Bin Detector CNN\n(PyTorch)"]
    cam["camera_stream.py\n(OpenCV)"]
    sm["main.py\nState Machine"]
    serial_mgr["arduino_serial.py\nSerial Manager"]
  end

  space:3

  block:ard1["⚙️ Arduino 1 — Car Controller"]:1
    columns 1
    l298n["L298N\nH-Bridge Driver"]
    motors["2× DC\nGear Motors"]
    watchdog["1s Watchdog\nTimer"]
  end

  space:1

  block:ard2["🦾 Arduino 2 — Arm Controller"]:1
    columns 1
    uln["3× ULN2003\nDrivers"]
    steppers["3× 28BYJ-48\nStepper Motors"]
    servo["SG90 Servo\n(Clamp)"]
  end

  pi --> ard1
  pi --> ard2
```

---

## 2. Power Architecture Block Diagram

```mermaid
flowchart TD
    BAT["🔋 12V LiPo Battery Pack"]
    USBC["🔌 5V/3A USB-C Adapter\n(External)"]
    BUCK["⚡ LM2596 Buck Converter\n12V → 5V Regulated"]
    L298N["L298N VCC\n(Motor Driver)"]
    MOT1["DC Motor LEFT"]
    MOT2["DC Motor RIGHT"]
    ARD1["Arduino UNO #1\n(Car Controller)"]
    ARD2["Arduino UNO #2\n(Arm Controller)"]
    ULN1["ULN2003 Board #1\n(Base Stepper)"]
    ULN2["ULN2003 Board #2\n(Joint Stepper)"]
    ULN3["ULN2003 Board #3\n(Ext Stepper)"]
    SERVO["SG90 Servo\n(Clamp)"]
    PI["Raspberry Pi 4\n1.8GHz ARM, 4GB RAM"]
    GND["⏚ Common Ground Bus"]

    BAT -->|"12V"| L298N
    BAT -->|"12V"| BUCK
    BUCK -->|"5V"| ARD1
    BUCK -->|"5V"| ARD2
    BUCK -->|"5V"| ULN1
    BUCK -->|"5V"| ULN2
    BUCK -->|"5V"| ULN3
    BUCK -->|"5V"| SERVO
    USBC -->|"5V/3A"| PI
    L298N -->|"PWM"| MOT1
    L298N -->|"PWM"| MOT2
    BAT -.->|"GND"| GND
    ARD1 -.->|"GND"| GND
    ARD2 -.->|"GND"| GND
    ULN1 -.->|"GND"| GND
    ULN2 -.->|"GND"| GND
    ULN3 -.->|"GND"| GND
    SERVO -.->|"GND"| GND

    style GND fill:#1a1a1a,color:#ffcc00,stroke:#ffcc00
    style BAT fill:#2d6a1f,color:#fff,stroke:#4caf50
    style PI fill:#3b1f6a,color:#fff,stroke:#9c27b0
    style BUCK fill:#6a3b1f,color:#fff,stroke:#ff9800
```

---

## 3. Main State Machine Flowchart

```mermaid
flowchart TD
    START([🚀 System Boot\nmain.py]) --> INIT["Initialize Subsystems:\n• Serial ports (2× Arduino)\n• Camera (OpenCV)\n• Flask Web Server\n• Load CNN models (if exist)"]
    INIT --> CONNECTED{"All connections\nestablished?"}
    CONNECTED -->|"No"| RETRY["Retry / Log Error\n(auto-reconnect loop)"]
    RETRY --> CONNECTED
    CONNECTED -->|"Yes"| MANUAL

    MANUAL(["🕹️ MANUAL MODE\n(Default)"])
    MANUAL --> MAN_CAM["Stream camera → MJPEG\nAccept HTTP commands"]
    MAN_CAM --> MAN_CMD{"User HTTP\nCommand?"}
    MAN_CMD -->|"Car command"| MAN_CAR["JSON → Arduino 1\n(motors)"]
    MAN_CMD -->|"Arm command"| MAN_ARM["JSON → Arduino 2\n(arm/clamp)"]
    MAN_CMD -->|"Switch mode"| MODE_SWITCH{"Target\nMode?"}
    MAN_CAR --> MANUAL
    MAN_ARM --> MANUAL

    MODE_SWITCH -->|"Training"| TRAINING
    MODE_SWITCH -->|"Autonomous"| CHECK_MODEL{"Driving model\nexists?"}
    CHECK_MODEL -->|"No"| WARN["⚠️ Show Warning:\nTrain model first"]
    WARN --> MANUAL
    CHECK_MODEL -->|"Yes"| AUTONOMOUS

    TRAINING(["📷 TRAINING MODE"])
    TRAINING --> TRAIN_DRIVE["User drives manually\n(W A S D keys)"]
    TRAIN_DRIVE --> SAVE_FRAME["Save frame to\ndata/driving/<label>/"]
    SAVE_FRAME --> TRAIN_CMD{"Mode switch\nto Manual?"}
    TRAIN_CMD -->|"No"| TRAIN_DRIVE
    TRAIN_CMD -->|"Yes"| TRAIN_BG["🔄 Launch background\nPyTorch training thread"]
    TRAIN_BG --> TRAIN_EPOCHS["Train 10 epochs\n(CompactCNN, SGD)"]
    TRAIN_EPOCHS --> SAVE_MODEL["Save → models/driving_model.pth\nHot-reload into inference engine"]
    SAVE_MODEL --> NOTIFY["✅ Show 'Model Ready'\non dashboard HUD"]
    NOTIFY --> MANUAL

    AUTONOMOUS(["🤖 AUTONOMOUS MODE"])
    AUTONOMOUS --> FRAME["Capture camera frame\n(~15 fps)"]
    FRAME --> RESIZE["Resize → 64×64 RGB"]
    RESIZE --> INFER_BOTH["Run both CNNs in parallel"]

    INFER_BOTH --> DRV_INF["Driving CNN\nargmax → label"]
    INFER_BOTH --> BIN_INF["Bin Detector CNN\nmax confidence"]

    DRV_INF --> SEND_MOTOR["JSON motor cmd\n→ Arduino 1"]
    SEND_MOTOR --> BIN_CHECK{"Bin confidence\n> 85%?"}
    BIN_INF --> BIN_CHECK

    BIN_CHECK -->|"No"| FRAME
    BIN_CHECK -->|"Yes"| STOP_CAR["Stop car\n(speed = 0)"]
    STOP_CAR --> COLLECT["Execute ARM_COLLECT_SEQUENCE\n(11 steps)"]
    COLLECT --> RESUME["Resume autonomous\nnavigation"]
    RESUME --> FRAME

    MODE_SWITCH2{"Mode switch\nfrom autonomous?"} --> AUTONOMOUS
    AUTONOMOUS -.->|"Manual override"| MANUAL

    style MANUAL fill:#1a4a8a,color:#fff,stroke:#2196F3
    style TRAINING fill:#4a2a8a,color:#fff,stroke:#9c27b0
    style AUTONOMOUS fill:#1a6a1a,color:#fff,stroke:#4caf50
    style START fill:#6a1a1a,color:#fff,stroke:#f44336
```

---

## 4. Dual-CNN Inference Pipeline

```mermaid
flowchart LR
    CAM["📷 USB Webcam\n1080p @ 30fps"]
    CAP["OpenCV VideoCapture\ncamera_stream.py\n(background thread)"]
    QUEUE["Frame Queue\n(thread-safe)"]
    RESIZE["Resize to 64×64\nPIL → Tensor\nNormalize [0,1]"]

    subgraph CNN_PARALLEL["⚡ Parallel Inference (model_inference.py)"]
        direction TB
        DRV["🚗 Driving CNN\n(CompactCNN)\n4-class output\n[fwd|left|right|stop]"]
        BIN["🗑️ Bin Detector CNN\n(CompactCNN)\n2-class output\n[bg|bin]"]
    end

    ARGMAX["argmax(output)\n→ direction label"]
    SOFTMAX["softmax confidence\n→ probability"]

    CMD_CAR["JSON Motor Command\n{cmd:move, dir:fwd, speed:200}"]
    THRESH{"confidence\n> 0.85?"}
    ARM_SEQ["Trigger\nARM_COLLECT_SEQUENCE"]

    ARD1["Arduino 1\n(L298N Motors)"]
    ARD2["Arduino 2\n(Arm + Servo)"]

    CAM --> CAP --> QUEUE --> RESIZE
    RESIZE --> DRV
    RESIZE --> BIN
    DRV --> ARGMAX --> CMD_CAR --> ARD1
    BIN --> SOFTMAX --> THRESH
    THRESH -->|"Yes"| ARM_SEQ --> ARD2
    THRESH -->|"No"| QUEUE

    style CNN_PARALLEL fill:#1a1a3a,color:#fff,stroke:#3f51b5,stroke-dasharray:5
    style DRV fill:#0d3a6e,color:#fff,stroke:#2196F3
    style BIN fill:#3a0d0d,color:#fff,stroke:#f44336
```

---

## 5. Robotic Arm Architecture Diagram

```mermaid
flowchart TD
    BASE_MOTOR["🔄 Base Stepper\n28BYJ-48 #1\n(Azimuth Rotation ±180°)"]
    JOINT_MOTOR["⬆️ Joint Stepper\n28BYJ-48 #2\n(Elevation Raise/Lower)"]
    EXT_MOTOR["↔️ Extension Stepper\n28BYJ-48 #3\n(Radial Reach)"]
    SERVO["🤏 SG90 Servo\n(Clamp: 0°–180°)"]
    CAM["📷 USB Webcam\n(End-effector mounted)"]

    subgraph ARM["🦾 4-DOF Serial Robotic Arm (Front of Chassis)"]
        direction BT
        CHASSIS["🚗 Car Chassis\n(Robot Base)"]
        BASE["BASE JOINT\nMounts to chassis\nRotates L/R"]
        LINK1["LINK 1\n(Rigid)"]
        JOINT["ELBOW JOINT\nRaises / Lowers arm"]
        LINK2["LINK 2\n(Rigid)"]
        EXT["EXTENSION JOINT\nExtends / Retracts reach"]
        CLAMP["CLAMP MECHANISM\n(Servo-driven gripper)"]
        CAMERA_MOUNT["📷 Camera Mount\n(Below clamp)"]

        CHASSIS --> BASE --> LINK1 --> JOINT --> LINK2 --> EXT --> CLAMP --> CAMERA_MOUNT
    end

    BASE_MOTOR -->|"ULN2003 #1\nPins 2,3,4,5"| BASE
    JOINT_MOTOR -->|"ULN2003 #2\nPins 6,7,8,9"| JOINT
    EXT_MOTOR -->|"ULN2003 #3\nPins 10,11,12,13"| EXT
    SERVO -->|"Signal → A0"| CLAMP
    CAM -->|"USB → Raspberry Pi"| CAMERA_MOUNT

    style ARM fill:#0d2a0d,stroke:#4caf50,color:#fff,stroke-width:2px
```

---

## 6. Garbage Collection Sequence Flowchart

```mermaid
flowchart TD
    DETECT(["🗑️ BIN DETECTED\nconfidence > 85%"])

    S1["Step 1: Open Clamp\nServo → 10°"]
    S2["Step 2: Extend Arm\nExtension Stepper → FWD +N steps"]
    S3["Step 3: Lower Arm\nJoint Stepper → DOWN -M steps"]
    S4["Step 4: Grab Bin\nServo → 70° (clamp shut)"]
    S5["Step 5: Lift Arm\nJoint Stepper → UP +200 steps"]
    S6["Step 6: Swing to Storage\nBase Stepper → +180 steps"]
    S7["Step 7: Dump Contents\nServo → 170° (upside-down tilt)"]
    S8["Step 8: Level Clamp\nServo → 70°"]
    S9["Step 9: Swing Back\nBase Stepper → -180 steps"]
    S10["Step 10: Lower to Ground\nJoint Stepper → DOWN -M steps"]
    S11["Step 11: Release Bin\nServo → 10°\nRetract Extension\nReturn Joint Home"]
    RESUME(["▶️ Resume\nAutonomous Driving"])

    DETECT --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10 --> S11 --> RESUME

    style DETECT fill:#6a1a1a,color:#fff,stroke:#f44336
    style RESUME fill:#1a6a1a,color:#fff,stroke:#4caf50
    style S4 fill:#1a3a6a,color:#fff,stroke:#2196F3
    style S7 fill:#3a1a6a,color:#fff,stroke:#9c27b0
```

---

## 7. Training Pipeline Flowchart

```mermaid
flowchart TD
    USER_DRIVE(["👤 User: Switch to\nTRAINING MODE"])
    DRIVE["User Drives Robot\nManually (W A S D)"]

    KEY_W["Key W → forward/"]
    KEY_A["Key A → left/"]
    KEY_S["Key S → stop/"]
    KEY_D["Key D → right/"]

    SAVE["data_recorder.py\nSaves frame to\ndata/driving/<label>/frame_NNNN.jpg"]
    COUNT{"Frame count\n≥ 2000?"}
    CONTINUE["Continue\ndriving..."]
    EXIT_TRAINING["User: Switch to\nMANUAL MODE"]

    subgraph TRAIN_THREAD["🔄 Background Training Thread (training_pipeline.py)"]
        LOAD["Load ImageFolder\n(data/driving/)"]
        SPLIT["Train/Val Split\n80% / 20%"]
        AUGMENT["Data Augmentation\nH-flip, Brightness jitter"]
        INIT_MODEL["Initialize\nCompactCNN (PyTorch)"]
        LOOP["Train Loop\n10 Epochs\nSGD lr=0.01 momentum=0.9"]
        VALIDATE["Validate Accuracy\neach epoch"]
        SAVE_MODEL["Save best weights\nmodels/driving_model.pth"]
        HOTRELOAD["Hot-reload model\ninto inference engine"]
    end

    HUD_YELLOW["🟡 Dashboard HUD\n'Compiling...' bar"]
    HUD_GREEN["🟢 Dashboard HUD\n'Model Ready'"]
    READY(["✅ Driving Model\nReady for Autonomous Mode"])

    USER_DRIVE --> DRIVE
    DRIVE --> KEY_W & KEY_A & KEY_S & KEY_D
    KEY_W & KEY_A & KEY_S & KEY_D --> SAVE --> COUNT
    COUNT -->|"No"| CONTINUE --> DRIVE
    COUNT -->|"Recommended"| EXIT_TRAINING
    EXIT_TRAINING --> HUD_YELLOW
    EXIT_TRAINING --> LOAD
    LOAD --> SPLIT --> AUGMENT --> INIT_MODEL --> LOOP --> VALIDATE --> SAVE_MODEL --> HOTRELOAD
    HOTRELOAD --> HUD_GREEN --> READY

    style TRAIN_THREAD fill:#1a1a4a,stroke:#3f51b5,color:#fff,stroke-dasharray:5
    style USER_DRIVE fill:#6a3a1a,color:#fff,stroke:#ff9800
    style READY fill:#1a6a1a,color:#fff,stroke:#4caf50
    style HUD_YELLOW fill:#5a5a00,color:#fff,stroke:#ffff00
    style HUD_GREEN fill:#005a1a,color:#fff,stroke:#00ff44
```

---

## 8. Serial Communication Protocol Flowchart

```mermaid
sequenceDiagram
    participant WEB as 🌐 Web Browser
    participant FLASK as 🐍 Flask Server<br/>(web_interface.py)
    participant SERIAL as 📡 ArduinoSerial<br/>(arduino_serial.py)
    participant ARD1 as ⚙️ Arduino 1<br/>(Car / L298N)
    participant ARD2 as 🦾 Arduino 2<br/>(Arm / Steppers)

    Note over WEB,ARD2: Manual Drive Example
    WEB->>FLASK: POST /car_command<br/>{"dir":"forward","speed":200}
    FLASK->>SERIAL: send_command(car_port, json)
    SERIAL->>ARD1: {"cmd":"move","dir":"forward","speed":200}\n
    ARD1->>ARD1: Set ENA/ENB PWM<br/>Set IN1–IN4 direction
    ARD1->>SERIAL: {"status":"ok"}\n
    SERIAL->>FLASK: ok
    FLASK->>WEB: 200 OK

    Note over WEB,ARD2: Arm Collect Sequence (Autonomous)
    FLASK->>SERIAL: send_command(arm_port, step_1)
    SERIAL->>ARD2: {"cmd":"clamp","angle":10}\n
    ARD2->>ARD2: Set servo PWM → 10°
    ARD2->>SERIAL: {"status":"ok"}\n
    SERIAL->>FLASK: ok (proceed to step 2)
    FLASK->>SERIAL: send_command(arm_port, step_2)
    SERIAL->>ARD2: {"cmd":"arm","motor":"ext","steps":150,"dir":1}\n
    ARD2->>ARD2: Run stepper half-step loop
    ARD2->>SERIAL: {"status":"ok"}\n

    Note over ARD1: Watchdog Safety
    SERIAL-->>ARD1: keepalive {"cmd":"ping"} every 500ms
    ARD1->>ARD1: If no msg for 1000ms:<br/>AUTO-STOP motors
```

---

## 9. Web Dashboard Architecture Diagram

```mermaid
flowchart TB
    subgraph BROWSER["🌐 Web Browser (any device, same WiFi)"]
        direction LR
        LEFT["LEFT PANEL\n━━━━━━━━━━━━━━\n📹 MJPEG Camera Feed\n   + HUD Overlay\n━━━━━━━━━━━━━━\n🕹️ Steering D-Pad\n   W / A / S / D\n   Speed Slider\n━━━━━━━━━━━━━━\n🦾 Arm Override\n   Stepper Buttons\n   Clamp Slider"]
        RIGHT["RIGHT PANEL\n━━━━━━━━━━━━━━\n⚙️ Mode Buttons\n   [Manual]\n   [Training]\n   [Autonomous]\n━━━━━━━━━━━━━━\n🔌 Diagnostics\n   Arduino status\n   Connection LEDs\n━━━━━━━━━━━━━━\n🎯 Target\n   Detection status\n   Confidence %"]
    end

    subgraph FLASK["🐍 Flask Application (Raspberry Pi :5000)"]
        ROUTE_ROOT["GET /\nServe dashboard.html"]
        ROUTE_VIDEO["GET /video_feed\nMJPEG multipart stream"]
        ROUTE_MODE["POST /mode\nSwitch state machine"]
        ROUTE_CAR["POST /car_command\nRelay → Arduino 1"]
        ROUTE_ARM["POST /arm_command\nRelay → Arduino 2"]
        ROUTE_STATUS["GET /status\nDiagnostics JSON"]
    end

    LEFT <-->|"AJAX / Fetch API"| ROUTE_ROOT
    LEFT <-->|"img src=  /video_feed"| ROUTE_VIDEO
    RIGHT <-->|"POST JSON"| ROUTE_MODE
    LEFT <-->|"POST JSON"| ROUTE_CAR
    LEFT <-->|"POST JSON"| ROUTE_ARM
    RIGHT <-->|"AJAX poll"| ROUTE_STATUS

    style BROWSER fill:#0d1a2a,stroke:#2196F3,color:#fff,stroke-width:2px
    style FLASK fill:#0d2a0d,stroke:#4caf50,color:#fff,stroke-width:2px
```

---

## 10. Arduino Wiring Block Diagrams

### Arduino 1 — Car Motor Controller

```mermaid
flowchart LR
    RPI1["Raspberry Pi 4\n(USB-A)"]
    ARD1["Arduino UNO #1"]

    subgraph L298N_BLOCK["L298N H-Bridge Module"]
        ENA["ENA\n(PWM Speed L)"]
        IN1["IN1 Direction"]
        IN2["IN2 Direction"]
        IN3["IN3 Direction"]
        IN4["IN4 Direction"]
        ENB["ENB\n(PWM Speed R)"]
        VCC["VCC (12V from Battery)"]
        GND_L["GND"]
        OUT12["OUT1+OUT2"]
        OUT34["OUT3+OUT4"]
    end

    MOTOR_L["⚙️ Left DC\nGear Motor"]
    MOTOR_R["⚙️ Right DC\nGear Motor"]
    BAT12V["🔋 12V Battery"]

    RPI1 -->|"USB Serial\n115200 baud"| ARD1
    ARD1 -->|"Pin 9 (PWM)"| ENA
    ARD1 -->|"Pin 8"| IN1
    ARD1 -->|"Pin 7"| IN2
    ARD1 -->|"Pin 5"| IN3
    ARD1 -->|"Pin 4"| IN4
    ARD1 -->|"Pin 3 (PWM)"| ENB
    BAT12V --> VCC
    OUT12 --> MOTOR_L
    OUT34 --> MOTOR_R

    style L298N_BLOCK fill:#1a2a0d,stroke:#8bc34a,color:#fff
```

### Arduino 2 — Robotic Arm Controller

```mermaid
flowchart LR
    RPI2["Raspberry Pi 4\n(USB-A)"]
    ARD2["Arduino UNO #2"]

    subgraph ULN_BASE["ULN2003 Board #1\n(Base Stepper)"]
        B_IN1["IN1"] & B_IN2["IN2"] & B_IN3["IN3"] & B_IN4["IN4"]
    end
    subgraph ULN_JOINT["ULN2003 Board #2\n(Joint Stepper)"]
        J_IN1["IN1"] & J_IN2["IN2"] & J_IN3["IN3"] & J_IN4["IN4"]
    end
    subgraph ULN_EXT["ULN2003 Board #3\n(Ext Stepper)"]
        E_IN1["IN1"] & E_IN2["IN2"] & E_IN3["IN3"] & E_IN4["IN4"]
    end

    STEP1["28BYJ-48\nBase Stepper"]
    STEP2["28BYJ-48\nJoint Stepper"]
    STEP3["28BYJ-48\nExt Stepper"]
    SERVO_HW["SG90\nServo"]

    RPI2 -->|"USB Serial"| ARD2
    ARD2 -->|"Pins 2,3,4,5"| B_IN1 & B_IN2 & B_IN3 & B_IN4
    ARD2 -->|"Pins 6,7,8,9"| J_IN1 & J_IN2 & J_IN3 & J_IN4
    ARD2 -->|"Pins 10,11,12,13"| E_IN1 & E_IN2 & E_IN3 & E_IN4
    ARD2 -->|"Pin A0\n(PWM Signal)"| SERVO_HW

    ULN_BASE --> STEP1
    ULN_JOINT --> STEP2
    ULN_EXT --> STEP3

    style ULN_BASE fill:#1a0d2a,stroke:#9c27b0,color:#fff
    style ULN_JOINT fill:#0d1a2a,stroke:#2196F3,color:#fff
    style ULN_EXT fill:#2a1a0d,stroke:#ff9800,color:#fff
```

---

## 11. Software Module Dependency Diagram

```mermaid
flowchart TD
    MAIN["main.py\n(Entry Point + State Machine)"]
    CONFIG["config.py\n(All Parameters)"]
    WEB["server/web_interface.py\n(Flask Routes)"]
    DASH["server/templates/dashboard.html\n(Browser UI)"]
    CAM_S["vision/camera_stream.py\n(OpenCV Capture + MJPEG)"]
    INFER["vision/model_inference.py\n(Dual CNN Inference)"]
    RECORDER["vision/data_recorder.py\n(Training Frame Saver)"]
    MOTOR["control/motor_control.py\n(DC Motor Abstraction)"]
    ARM["control/arm_control.py\n(Arm Sequence Executor)"]
    SERIAL["communication/arduino_serial.py\n(Thread-safe Serial)"]
    ML["ml/training_pipeline.py\n(CompactCNN + Trainer)"]
    TORCH["torch / torchvision"]
    CV["opencv-python (cv2)"]
    FLASK_LIB["flask + flask-cors"]
    PYSERIAL["pyserial"]
    MODELS["models/*.pth\n(Saved Weights)"]
    DATA["data/driving/\n(Training Frames)"]

    MAIN --> WEB & CAM_S & INFER & RECORDER & MOTOR & ARM & ML
    WEB --> DASH
    INFER --> TORCH
    INFER --> MODELS
    ML --> TORCH
    ML --> DATA
    ML --> MODELS
    CAM_S --> CV
    MOTOR --> SERIAL
    ARM --> SERIAL
    SERIAL --> PYSERIAL
    WEB --> FLASK_LIB
    MAIN --> CONFIG
    ML --> CONFIG
    ARM --> CONFIG
    MOTOR --> CONFIG
    RECORDER --> DATA

    style MAIN fill:#1a1a4a,color:#fff,stroke:#3f51b5
    style CONFIG fill:#4a1a1a,color:#fff,stroke:#f44336
    style TORCH fill:#2a4a1a,color:#fff,stroke:#8bc34a
    style FLASK_LIB fill:#1a3a4a,color:#fff,stroke:#00bcd4
```

---

*Diagrams generated for: Autonomous Garbage Collector Robot*  
*GitHub: https://github.com/rakesh-i/ESP32-Autonomous-car*  
*Format: A4 — All diagrams are Mermaid-compatible*

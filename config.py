"""
config.py — Central configuration for the Raspberry Pi 4B Garbage Collector Robot.

Hardware defaults are defined here. User-tunable values (camera index, serial ports,
speeds, etc.) can be overridden at runtime via the web dashboard and are stored in
user_settings.json by runtime_config.py.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# PLATFORM
# ─────────────────────────────────────────────
PI_MODEL = "Raspberry Pi 4B"
HOTSPOT_IP = "192.168.4.1"

# ─────────────────────────────────────────────
# SERIAL / ARDUINO
# ─────────────────────────────────────────────
CAR_SERIAL_PORT   = "/dev/ttyUSB0"   # Arduino 1 — DC motor car
ARM_SERIAL_PORT   = "/dev/ttyUSB1"   # Arduino 2 — ULN2003 steppers + servo
SERIAL_BAUD_RATE  = 115200
SERIAL_TIMEOUT    = 1.0              
SERIAL_RECONNECT_DELAY = 3.0        

# ─────────────────────────────────────────────
# CAMERA  (Pi 4B USB webcam optimized)
# ─────────────────────────────────────────────
CAMERA_INDEX   = 0
CAMERA_WIDTH   = 640       # Pi 4B realistic — was 1920
CAMERA_HEIGHT  = 480       # Pi 4B realistic — was 1080
CAMERA_FPS     = 30        # Increased for smoother website feed

STREAM_WIDTH   = 320
STREAM_HEIGHT  = 240

# ─────────────────────────────────────────────
# FLASK SERVER
# ─────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# ─────────────────────────────────────────────
# CAR MOTOR SPEEDS
# ─────────────────────────────────────────────
DEFAULT_SPEED = 180
MAX_SPEED     = 255
MIN_SPEED     = 80
TURN_SPEED    = 160

# ─────────────────────────────────────────────
# MACHINE LEARNING / INFERENCE (DUAL MODELS)
# ─────────────────────────────────────────────
MODELS_DIR           = os.path.join(BASE_DIR, "models")
GARBAGE_BIN_MODEL    = os.path.join(MODELS_DIR, "garbage_bin.pth")
DRIVING_MODEL        = os.path.join(MODELS_DIR, "driving_model.pth")
DATA_DIR             = os.path.join(BASE_DIR, "data")
DRIVING_DATA_DIR     = os.path.join(DATA_DIR, "driving")

MODEL_INPUT_WIDTH    = 160   # Lower resolution for faster dual inference
MODEL_INPUT_HEIGHT   = 120

# Garbage Bin Classes
BIN_CLASSES = ["background", "garbage_bin"]
BIN_DETECT_THRESHOLD = 0.85

# Driving Classes (Simple Classification: 0=Left, 1=Forward, 2=Right, 3=Stop)
DRIVING_CLASSES = ["left", "forward", "right", "stop"]

# APPROACH LOGIC
APPROACH_SPEED = 140

# ─────────────────────────────────────────────
# LINE DETECTION (PID CONTROLLER)
# Used by vision/line_detection.py (optional module)
# ─────────────────────────────────────────────
LINE_REGION_Y = 0.3        # Bottom 30% of the frame is the ROI
LINE_COLOR    = "black"    # "black" line on white floor, or "white" on dark floor

PID_KP = 0.4              # Proportional gain
PID_KI = 0.0              # Integral gain
PID_KD = 0.1              # Derivative gain

# ─────────────────────────────────────────────
# ARM — ULN2003 STEPPER PARAMATERS
# ─────────────────────────────────────────────
STEPPER_STEP_DELAY_MS = 4

CLAMP_OPEN_ANGLE  = 10    # Open wide
CLAMP_CLOSE_ANGLE = 70    # Grip bin securely
CLAMP_DUMP_ANGLE  = 170   # Tilt backward/down to dump

# ─────────────────────────────────────────────
# GARBAGE BIN COLLECTION SEQUENCE
# Goal: Grab bin, Lift, Dump into car bed, Replace bin on ground, Release.
# ─────────────────────────────────────────────
ARM_COLLECT_SEQUENCE = [
    # 1. Open clamp wide
    {"action": "clamp",  "angle": CLAMP_OPEN_ANGLE},
    {"action": "wait",   "ms": 500},
    
    # 2. Extend & Lower to Bin
    {"action": "arm",    "motor": "ext",   "steps": 250, "dir": 1},
    {"action": "arm",    "motor": "joint", "steps": 120, "dir": 1},
    {"action": "wait",   "ms": 300},
    
    # 3. Close Clamp (Grab Bin)
    {"action": "clamp",  "angle": CLAMP_CLOSE_ANGLE},
    {"action": "wait",   "ms": 500},
    
    # 4. Lift Bin Up
    {"action": "arm",    "motor": "joint", "steps": 200, "dir": 0},
    {"action": "wait",   "ms": 200},
    
    # 5. Swing Base to Car Storage (Assume 180 steps puts arm over back of car)
    {"action": "arm",    "motor": "base",  "steps": 180, "dir": 1},
    {"action": "wait",   "ms": 400},
    
    # 6. Tilt Clamp to Dump Contents
    {"action": "clamp",  "angle": CLAMP_DUMP_ANGLE},
    {"action": "wait",   "ms": 1000},  # Wait for trash to fall out
    
    # 7. Level Clamp again
    {"action": "clamp",  "angle": CLAMP_CLOSE_ANGLE},
    {"action": "wait",   "ms": 300},
    
    # 8. Swing Base back to front (Replace position)
    {"action": "arm",    "motor": "base",  "steps": 180, "dir": 0},
    {"action": "wait",   "ms": 300},
    
    # 9. Lower to ground
    {"action": "arm",    "motor": "joint", "steps": 200, "dir": 1},
    {"action": "wait",   "ms": 300},
    
    # 10. Open Clamp (Release Bin)
    {"action": "clamp",  "angle": CLAMP_OPEN_ANGLE},
    {"action": "wait",   "ms": 500},
    
    # 11. Return to Home (Retract & Raise)
    {"action": "arm",    "motor": "ext",   "steps": 250, "dir": 0},
    {"action": "arm",    "motor": "joint", "steps": 120, "dir": 0},
]

# ARM HOME POSITION (used for arm reset/calibration from dashboard)
ARM_HOME_POSITION = {
    "clamp_angle": CLAMP_OPEN_ANGLE,
}

LOG_LEVEL = "INFO"

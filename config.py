"""
config.py — Central configuration for the Raspberry Pi Garbage Collector Robot.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# SERIAL / ARDUINO
# ─────────────────────────────────────────────
CAR_SERIAL_PORT   = "/dev/ttyUSB0"   # Arduino 1 — DC motor car
ARM_SERIAL_PORT   = "/dev/ttyUSB1"   # Arduino 2 — ULN2003 steppers + servo
SERIAL_BAUD_RATE  = 115200
SERIAL_TIMEOUT    = 1.0              
SERIAL_RECONNECT_DELAY = 3.0        

# ─────────────────────────────────────────────
# CAMERA
# ─────────────────────────────────────────────
CAMERA_INDEX   = 0
CAMERA_WIDTH   = 1920
CAMERA_HEIGHT  = 1080
CAMERA_FPS     = 30

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

LOG_LEVEL = "INFO"

import time
import logging
import threading
import sys
import signal
import os

import config
from communication.arduino_serial import SerialManager
from control.motor_control import MotorController
from control.arm_control import ArmController
from vision.camera_stream import CameraStream
from vision.model_inference import DualModelInference
from vision.data_recorder import DataRecorder
from server.web_interface import WebServer
from runtime_config import runtime_cfg

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RobotState:
    """Shared state across threads."""
    def __init__(self):
        self.mode = "manual"  # manual, training, autonomous
        self.running = True
        
        # Subsystems
        self.serial = None
        self.motors = None
        self.arm = None
        self.camera = None
        self.dual_inference = None
        self.data_recorder = None
        self.web_server = None
        
        # UI & Inter-thread states
        self.last_car_command = "stop"
        self.training_status = "idle"     # idle, training, done, error
        self.training_progress = 0
        
        # Inference results
        self.bin_detected = False
        self.bin_score = 0.0
        self.bin_box = None
        
        # Arm Recording
        self.recording_arm = False
        self.recorded_arm_sequence = []
        self.last_arm_cmd_time = 0.0


def inference_worker(state):
    """Background thread to run ML Inference so it doesn't block the main loop."""
    logger.info("Starting inference background thread...")
    while state.running:
        if state.mode in ["autonomous", "follow-and-collect"]:
            if not state.dual_inference:
                time.sleep(0.5)
                continue
                
            frame = state.camera.get_frame() if state.camera else None
            if frame is None:
                time.sleep(0.1)
                continue
                
            driving_cmd, bin_det, bin_score, bin_box = state.dual_inference.predict(frame)
            state.bin_detected = bin_det
            state.bin_score = bin_score
            state.bin_box = bin_box
            state.last_car_command = driving_cmd
            
        else:
            state.bin_detected = False
            state.bin_score = 0.0
            state.bin_box = None
            time.sleep(0.1)


def print_banner():
    """Print startup banner with system info."""
    print("""
╔══════════════════════════════════════════════════╗
║   🤖 Autonomous Garbage Collector Robot v2.0    ║
║   Platform: Raspberry Pi 4B                      ║
╚══════════════════════════════════════════════════╝
""")
    logger.info(f"Dashboard URL: http://{config.HOTSPOT_IP}:{config.FLASK_PORT}")
    logger.info(f"Connect to WiFi: {runtime_cfg.get('hotspot_ssid', 'GarbageBot')}")


def main():
    print_banner()
    state = RobotState()
    
    # Ensure required directories exist
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    os.makedirs(config.DRIVING_DATA_DIR, exist_ok=True)
    for cls in config.DRIVING_CLASSES:
        os.makedirs(os.path.join(config.DRIVING_DATA_DIR, cls), exist_ok=True)
    
    # ── Init Serial (graceful — won't crash if Arduinos absent) ──
    logger.info("Connecting to Arduinos...")
    state.serial = SerialManager()
    state.motors = MotorController(state.serial)
    state.arm = ArmController(state.serial)
    
    # Try to set clamp to open position
    try:
        state.arm.set_clamp(config.CLAMP_OPEN_ANGLE)
    except Exception as e:
        logger.warning(f"Could not set initial clamp position: {e}")
    
    # ── Init Camera ──
    camera_index = runtime_cfg.get("camera_index", config.CAMERA_INDEX)
    state.camera = CameraStream()
    if not state.camera.start(camera_index=camera_index):
        logger.error("⚠ Camera failed to start — video feed will be unavailable")
        logger.error("  → Connect a USB webcam and change camera index in Settings")
        # Don't exit — the dashboard is still useful for config
        
    # ── Init ML ──
    logger.info("Loading ML models...")
    try:
        state.dual_inference = DualModelInference()
    except Exception as e:
        logger.error(f"ML initialization failed: {e}")
        state.dual_inference = None
    
    state.data_recorder = DataRecorder()
    
    # ── Start Inference Thread ──
    inf_thread = threading.Thread(target=inference_worker, args=(state,), daemon=True)
    inf_thread.start()
    
    # ── Start Web Dashboard ──
    state.web_server = WebServer(state)
    state.web_server.start_background()
    
    # ── Print Summary ──
    logger.info("─── System Status ───")
    logger.info(f"  Car Arduino:  {'✓ Connected' if state.serial.car.connected else '✗ Not connected'}")
    logger.info(f"  Arm Arduino:  {'✓ Connected' if state.serial.arm.connected else '✗ Not connected'}")
    logger.info(f"  Camera:       {'✓ Running' if (state.camera and state.camera.running) else '✗ Not available'}")
    logger.info(f"  Driving CNN:  {'✓ Loaded' if (state.dual_inference and state.dual_inference.driving_loaded) else '✗ Not trained'}")
    logger.info(f"  Bin CNN:      {'✓ Loaded' if (state.dual_inference and state.dual_inference.bin_loaded) else '✗ Not loaded'}")
    logger.info(f"  Dashboard:    http://{config.HOTSPOT_IP}:{config.FLASK_PORT}")
    logger.info("─────────────────────")
    
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        state.running = False
        try:
            if state.motors: state.motors.stop()
        except Exception:
            pass
        try:
            if state.camera: state.camera.stop()
        except Exception:
            pass
        try:
            if state.serial: state.serial.close_all()
        except Exception:
            pass
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("System started. Press Ctrl+C to stop.")
    
    try:
        while state.running:
            frame = None
            if state.camera and state.camera.running:
                frame = state.camera.get_frame()
            
            if frame is None:
                time.sleep(0.1)
                continue

            # ---------------------------------------------------------
            # TRAINING MODE (DATA COLLECTION)
            # ---------------------------------------------------------
            if state.mode == "training":
                state.data_recorder.record_frame(frame.copy(), state.last_car_command)
                
            # ---------------------------------------------------------
            # AUTONOMOUS MODE
            # ---------------------------------------------------------
            elif state.mode == "autonomous":
                if state.arm and state.arm.sequence_running:
                    if state.motors:
                        state.motors.stop()
                    time.sleep(0.1)
                    continue

                # 1. High Priority: BIN DETECTED -> Collection Sequence
                if state.bin_detected:
                    if state.motors:
                        state.motors.stop()
                    logger.info("GARBAGE BIN DETECTED. Executing Arm Collection Sequence.")
                    if state.arm:
                        state.arm.trigger_collection_sequence()
                    time.sleep(1)
                    continue
                
                # 2. Lower Priority: DRIVING
                if state.last_car_command == "stop":
                    if state.motors:
                        state.motors.stop()
                else:
                    if state.motors:
                        state.motors.move(state.last_car_command, config.DEFAULT_SPEED)

            # ---------------------------------------------------------
            # FOLLOW-AND-COLLECT MODE
            # ---------------------------------------------------------
            elif state.mode == "follow-and-collect":
                if state.arm and state.arm.sequence_running:
                    if state.motors:
                        state.motors.stop()
                    time.sleep(0.1)
                    continue

                if state.bin_detected and state.bin_box is not None:
                    x, y, w, h = state.bin_box
                    center_x = x + w / 2

                    # Stop & collect if bin is large enough
                    # Stream resolution is 320x240
                    if w * h > (320 * 240 * 0.3): # > 30% of standard stream
                        if state.motors:
                            state.motors.stop()
                        logger.info("BIN IS CLOSE. Executing Arm Collection Sequence.")
                        if state.arm:
                            state.arm.trigger_collection_sequence()
                        time.sleep(1)
                        continue

                    # Proportional Steer
                    if center_x < (config.STREAM_WIDTH / 2) - 40:
                        cmd = "left"
                        speed = config.TURN_SPEED
                    elif center_x > (config.STREAM_WIDTH / 2) + 40:
                        cmd = "right"
                        speed = config.TURN_SPEED
                    else:
                        cmd = "forward"
                        speed = config.APPROACH_SPEED
                else:
                    cmd = "stop"
                    speed = 0

                if cmd == "stop":
                    if state.motors:
                        state.motors.stop()
                else:
                    if state.motors:
                        state.motors.move(cmd, speed)
            
            # ---------------------------------------------------------
            # MANUAL MODE
            # ---------------------------------------------------------
            else:
                pass

            time.sleep(0.05)  # ~20Hz Loop rate
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        signal_handler(None, None)

if __name__ == "__main__":
    main()

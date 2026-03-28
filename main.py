import time
import logging
import threading
import sys
import signal

import config
from communication.arduino_serial import SerialManager
from control.motor_control import MotorController
from control.arm_control import ArmController
from vision.camera_stream import CameraStream
from vision.model_inference import DualModelInference
from vision.data_recorder import DataRecorder
from server.web_interface import WebServer

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

def main():
    state = RobotState()
    
    # Init Interfaces
    state.serial = SerialManager()
    state.motors = MotorController(state.serial)
    state.arm = ArmController(state.serial)
    state.arm.set_clamp(config.CLAMP_OPEN_ANGLE)
    
    state.camera = CameraStream()
    if not state.camera.start():
        logger.error("Failed to start camera. Exiting.")
        sys.exit(1)
        
    state.dual_inference = DualModelInference()
    state.data_recorder = DataRecorder()
    
    state.web_server = WebServer(state)
    state.web_server.start_background()
    
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        state.running = False
        state.motors.stop()
        state.camera.stop()
        state.serial.close_all()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("System started. Press Ctrl+C to stop.")
    
    try:
        while state.running:
            frame = state.camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            # ---------------------------------------------------------
            # TRAINING MODE (DATA COLLECTION)
            # ---------------------------------------------------------
            if state.mode == "training":
                # Save the camera frame paired with whatever key the user is currently pressing
                state.data_recorder.record_frame(frame.copy(), state.last_car_command)
                
            # ---------------------------------------------------------
            # AUTONOMOUS MODE
            # ---------------------------------------------------------
            elif state.mode == "autonomous":
                if state.arm.sequence_running:
                    state.motors.stop()
                    time.sleep(0.1)
                    continue
                
                # Run the dual PyTorch CNNs!
                driving_cmd, bin_is_visible, bin_conf = state.dual_inference.predict(frame.copy())
                
                state.bin_detected = bin_is_visible
                state.bin_score = bin_conf
                state.last_car_command = driving_cmd

                # 1. High Priority: BIN DETECTED -> Collection Sequence
                if bin_is_visible:
                    # Car stops, Arm "approaches" (extends) and collects bin.
                    state.motors.stop()
                    logger.info("GARBAGE BIN DETECTED. Executing Arm Collection Sequence.")
                    state.arm.trigger_collection_sequence()
                    continue
                
                # 2. Lower Priority: DRIVING
                if driving_cmd == "stop":
                    state.motors.stop()
                else:
                    state.motors.move(driving_cmd, config.DEFAULT_SPEED)
            
            # ---------------------------------------------------------
            # MANUAL MODE
            # ---------------------------------------------------------
            else:
                # Direct UI Control handled async by Flask. Just pass time.
                state.bin_detected = False
                state.bin_score = 0.0

            time.sleep(0.05) # ~20Hz Loop rate
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        signal_handler(None, None)

if __name__ == "__main__":
    main()

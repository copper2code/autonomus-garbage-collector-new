import time
import logging
import threading
import config

logger = logging.getLogger(__name__)

class ArmController:
    """Controls the robotic arm's steppers and servo via Arduino 2."""
    
    def __init__(self, serial_manager):
        self.serial = serial_manager.arm
        self.sequence_running = False
        self.sequence_lock = threading.Lock()
        
    def execute_raw(self, motor: str, value: int):
        """
        Generic command receiver from Web UI.
        motor: "base", "joint", "ext", "clamp"
        value: steps (if stepper) or angle (if clamp)
        """
        if motor == "clamp":
            self.set_clamp(value)
        elif motor in ["base", "joint", "ext"]:
            # Basic convention: >0 is forward/up, <0 is backward/down
            direction = 1 if value >= 0 else 0
            steps = abs(value)
            self.move_stepper(motor, steps, direction)
        else:
            logger.warning(f"Unknown arm motor specifier: {motor}")

    def move_stepper(self, motor: str, steps: int, direction: int):
        """
        Commands a specific stepper motor.
        motor: "base", "joint", "ext"
        steps: number of steps to move
        direction: 1 (forward/up) or 0 (backward/down)
        """
        cmd = {
            "cmd": "arm",
            "motor": motor,
            "steps": steps,
            "dir": direction
        }
        logger.debug(f"Arm Stepper Cmd: {cmd}")
        self.serial.send_json(cmd)
        
    def set_clamp(self, angle: int):
        """
        Commands the clamp servo.
        angle: 0-180 degrees
        """
        angle = max(0, min(180, angle))
        cmd = {
            "cmd": "clamp",
            "angle": angle
        }
        logger.debug(f"Arm Servo Cmd: {cmd}")
        self.serial.send_json(cmd)

    def trigger_collection_sequence(self):
        """
        Executes the full garbage collection sequence in a background thread.
        Uses a lock to prevent concurrent triggers.
        """
        with self.sequence_lock:
            if self.sequence_running:
                logger.warning("Collection sequence already running, ignoring trigger.")
                return False
            self.sequence_running = True
            
        def runner():
            logger.info("Starting garbage collection sequence...")
            try:
                for step in config.ARM_COLLECT_SEQUENCE:
                    action = step.get("action")
                    if action == "clamp":
                        self.set_clamp(step["angle"])
                    elif action == "arm":
                        self.move_stepper(step["motor"], step["steps"], step["dir"])
                        # Approximate wait time for stepper to finish (ULN2003)
                        # Arduino executes asynchronously, so we wait on the Pi side before sending the next command to not overflow buffers
                        est_time = (step["steps"] * config.STEPPER_STEP_DELAY_MS) / 1000.0
                        time.sleep(est_time + 0.1)
                    elif action == "wait":
                        time.sleep(step["ms"] / 1000.0)
                logger.info("Garbage collection sequence completed.")
            except Exception as e:
                logger.error(f"Error during collection sequence: {e}")
            finally:
                with self.sequence_lock:
                    self.sequence_running = False

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        return True

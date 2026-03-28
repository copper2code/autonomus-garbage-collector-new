import logging
import config

logger = logging.getLogger(__name__)

class MotorController:
    """Controls the car's DC motors via Arduino 1."""
    
    def __init__(self, serial_manager):
        self.serial = serial_manager.car
        
    def move(self, direction: str, speed: int = config.DEFAULT_SPEED):
        """
        Commands the car to move.
        direction: "forward", "backward", "left", "right", "stop"
        speed: 0-255
        """
        # Constrain speed
        speed = max(0, min(config.MAX_SPEED, speed))
        
        cmd = {
            "cmd": "move",
            "dir": direction,
            "speed": speed
        }
        logger.debug(f"Car Cmd: {cmd}")
        self.serial.send_json(cmd)
        
    def stop(self):
        self.move("stop", 0)

    # Helper methods for direct API calls
    def forward(self, speed=config.DEFAULT_SPEED):
        self.move("forward", speed)
        
    def backward(self, speed=config.DEFAULT_SPEED):
        self.move("backward", speed)
        
    def left(self, speed=config.TURN_SPEED):
        self.move("left", speed)
        
    def right(self, speed=config.TURN_SPEED):
        self.move("right", speed)

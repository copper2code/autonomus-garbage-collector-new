import cv2
import numpy as np
import logging

import config

logger = logging.getLogger(__name__)

class LineDetector:
    """Detects black/white line and outputs an error (steering angle) using PID."""
    
    def __init__(self):
        # PID state
        self.last_error = 0
        self.integral = 0
        
    def process_frame(self, frame):
        """
        Takes a BGR frame from camera.
        Returns (steering_value, is_line_detected)
        steering_value: float suitable for mapping to car motor speeds
        """
        if frame is None:
            return 0.0, False

        height, width, _ = frame.shape
        
        # Look only at the bottom portion of the frame
        roi_top = int(height * (1.0 - config.LINE_REGION_Y))
        roi = frame[roi_top:height, 0:width]
        
        # Convert to grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Apply blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Simple thresholding
        # Depending on lighting, adaptive threshold might be needed.
        if config.LINE_COLOR == "black":
            # Black line on white floor
            _, thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY_INV)
        else:
            # White line on dark floor
            _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
            
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            # Choose the largest contour (assumes it's the line)
            c = max(contours, key=cv2.contourArea)
            M = cv2.moments(c)
            
            if M["m00"] != 0:
                cx = int(M['m10']/M['m00'])
                # cy = int(M['m01']/M['m00'])
                
                # Calculate error from center of the frame (0 = centered)
                center_x = width // 2
                error = cx - center_x
                
                # PID calculation
                dt = 0.1 # Approximate fixed time step
                self.integral += error * dt
                derivative = (error - self.last_error) / dt
                
                steering = (config.PID_KP * error) + (config.PID_KI * self.integral) + (config.PID_KD * derivative)
                
                self.last_error = error
                return steering, True
                
        # Line lost
        return 0, False

    def reset_pid(self):
        self.last_error = 0
        self.integral = 0

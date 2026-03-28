import os
import cv2
import time
import logging

import config

logger = logging.getLogger(__name__)

class DataRecorder:
    """Records camera frames mapping to steering commands for training."""
    def __init__(self):
        self.recording = False
        self.save_dir = config.DRIVING_DATA_DIR
        
        # Ensure mapping dirs exist
        for cls in config.DRIVING_CLASSES:
            os.makedirs(os.path.join(self.save_dir, cls), exist_ok=True)
            
        self.counter = 0

    def start(self):
        logger.info("Started Training Mode Recording.")
        self.recording = True

    def stop(self):
        logger.info(f"Stopped Training Mode Recording. Saved {self.counter} frames.")
        self.recording = False
        return self.counter

    def record_frame(self, frame, command):
        """Saves frame categorized by the current steering command."""
        if not self.recording or frame is None:
            return
            
        if command not in config.DRIVING_CLASSES:
            return
            
        # Format: data/driving/left/1234567.jpg
        # Save slightly lower res to preserve disk space and match model input
        save_frame = cv2.resize(frame, (config.MODEL_INPUT_WIDTH, config.MODEL_INPUT_HEIGHT))
        filepath = os.path.join(self.save_dir, command, f"{int(time.time()*1000)}.jpg")
        
        # Fast write
        cv2.imwrite(filepath, save_frame)
        self.counter += 1

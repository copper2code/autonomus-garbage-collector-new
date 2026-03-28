import cv2
import threading
import time
import logging

import config

logger = logging.getLogger(__name__)

class CameraStream:
    """Manages OpenCV VideoCapture and makes current frame available."""
    def __init__(self):
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        
    def start(self):
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        
        # Optionally set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        
        if not self.cap.isOpened():
            logger.error(f"Failed to open camera index {config.CAMERA_INDEX}")
            return False

        self.running = True
        logger.info(f"Camera started on index {config.CAMERA_INDEX}")
        
        # Start capture thread
        t = threading.Thread(target=self._update_frame, daemon=True)
        t.start()
        return True
        
    def _update_frame(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                # Downscale frame for processing/streaming efficiency
                frame = cv2.resize(frame, (config.STREAM_WIDTH, config.STREAM_HEIGHT))
                with self.lock:
                    self.frame = frame
            else:
                logger.warning("Camera dropped a frame")
                time.sleep(0.1)

    def get_frame(self):
        """Returns the most recent frame."""
        with self.lock:
            # Return a copy so the caller can modify it without affecting streamer
            return self.frame.copy() if self.frame is not None else None

    def get_mjpeg_frame(self, annotations=None):
        """Yields JPEG encoded frames for Flask streaming."""
        with self.lock:
            if self.frame is None:
                return None
            frame = self.frame.copy()

        # Optionally draw annotations on the stream frame
        if annotations:
            # Simple text overlay for HUD
            y0, dy = 30, 30
            for i, text in enumerate(annotations):
                y = y0 + i*dy
                cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return buffer.tobytes()

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

import cv2
import threading
import time
import logging

import config

logger = logging.getLogger(__name__)


class CameraStream:
    """Manages OpenCV VideoCapture with Pi 4B resilience and runtime switching."""
    
    def __init__(self):
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.camera_index = config.CAMERA_INDEX
        self.width = config.CAMERA_WIDTH
        self.height = config.CAMERA_HEIGHT
        self.fps = config.CAMERA_FPS
        
    def start(self, camera_index=None, retries=3, retry_delay=2.0):
        """Start camera with retry logic for Pi 4B USB enumeration delays."""
        if camera_index is not None:
            self.camera_index = camera_index
            
        for attempt in range(1, retries + 1):
            logger.info(f"Opening camera index {self.camera_index} (attempt {attempt}/{retries})...")
            
            # Use V4L2 backend explicitly for better Pi compatibility
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            
            if not self.cap.isOpened():
                # Fallback: try without explicit backend
                self.cap = cv2.VideoCapture(self.camera_index)
            
            if self.cap.isOpened():
                break
                
            logger.warning(f"Camera attempt {attempt} failed, waiting {retry_delay}s...")
            if self.cap:
                self.cap.release()
            time.sleep(retry_delay)
        
        if not self.cap or not self.cap.isOpened():
            logger.error(f"Failed to open camera index {self.camera_index} after {retries} attempts")
            return False

        # Set resolution — Pi 4B + USB webcam works best at 640x480
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Verify actual settings
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        logger.info(f"✓ Camera started: {actual_w}×{actual_h} @ {actual_fps}fps (index {self.camera_index})")

        self.running = True
        t = threading.Thread(target=self._update_frame, daemon=True)
        t.start()
        return True
        
    def _update_frame(self):
        consecutive_failures = 0
        max_failures = 30  # ~3 seconds of failures before logging error
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    consecutive_failures = 0
                    # Downscale for processing/streaming efficiency
                    frame = cv2.resize(frame, (config.STREAM_WIDTH, config.STREAM_HEIGHT))
                    with self.lock:
                        self.frame = frame
                else:
                    consecutive_failures += 1
                    if consecutive_failures == max_failures:
                        logger.error("Camera continuously dropping frames — check USB connection")
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Camera frame error: {e}")
                time.sleep(0.5)

    def get_frame(self):
        """Returns the most recent frame."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def get_mjpeg_frame(self, annotations=None):
        """Yields JPEG encoded frames for Flask streaming."""
        with self.lock:
            if self.frame is None:
                return None
            frame = self.frame.copy()

        # Optionally draw annotations on the stream frame
        if annotations:
            y0, dy = 30, 30
            for i, text in enumerate(annotations):
                y = y0 + i*dy
                cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return buffer.tobytes()

    def switch_camera(self, new_index):
        """Hot-switch to a different camera index (called from config dashboard)."""
        logger.info(f"Switching camera from index {self.camera_index} to {new_index}")
        self.stop()
        time.sleep(0.5)
        return self.start(camera_index=new_index)

    def get_available_cameras(self, max_check=5):
        """Probe which camera indices have devices (for the config dropdown)."""
        available = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available.append(i)
                cap.release()
        return available

    def stop(self):
        self.running = False
        time.sleep(0.2)  # Let capture thread exit
        if self.cap:
            self.cap.release()

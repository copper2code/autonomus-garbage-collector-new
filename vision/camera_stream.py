import cv2
import threading
import time
import logging

import config

logger = logging.getLogger(__name__)


class CameraStream:
    """
    Manages OpenCV VideoCapture optimized for Pi 4B.
    
    Key optimization: requests MJPEG output from the camera hardware
    so the Pi CPU doesn't have to encode raw frames to JPEG.
    """
    
    def __init__(self):
        self.cap = None
        self.frame = None           # Latest raw frame (for ML inference)
        self.jpeg_bytes = None      # Latest pre-encoded JPEG (for streaming)
        self.running = False
        self.lock = threading.Lock()
        self.camera_index = config.CAMERA_INDEX
        self.width = config.CAMERA_WIDTH
        self.height = config.CAMERA_HEIGHT
        self.fps = config.CAMERA_FPS
        self._frame_count = 0
        
    def start(self, camera_index=None, retries=3, retry_delay=2.0):
        """Start camera with retry logic for Pi 4B USB enumeration delays."""
        if camera_index is not None:
            self.camera_index = camera_index
            
        for attempt in range(1, retries + 1):
            logger.info(f"Opening camera index {self.camera_index} (attempt {attempt}/{retries})...")
            
            # Use V4L2 backend for better Pi compatibility
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

        # Request MJPEG output from camera hardware — avoids Pi CPU doing raw→JPEG
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        
        # Set resolution — Pi 4B + USB webcam works best at 640x480
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Minimize internal buffer — we only want the latest frame
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Verify actual settings
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
        logger.info(f"✓ Camera started: {actual_w}×{actual_h} @ {actual_fps}fps "
                     f"[{fourcc_str}] (index {self.camera_index})")

        self.running = True
        t = threading.Thread(target=self._capture_loop, daemon=True)
        t.start()
        return True
        
    def _capture_loop(self):
        """
        Capture thread: grabs frames and pre-encodes JPEG for streaming.
        Pre-encoding here means the web streaming endpoint doesn't block on imencode.
        """
        consecutive_failures = 0
        max_failures = 30
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 50]  # Quality 50 = good for Pi
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures == max_failures:
                        logger.error("Camera continuously dropping frames — check USB connection")
                    time.sleep(0.05)
                    continue
                
                consecutive_failures = 0
                self._frame_count += 1
                
                # Resize for processing
                small = cv2.resize(frame, (config.STREAM_WIDTH, config.STREAM_HEIGHT))
                
                # Pre-encode JPEG in this thread (not in the Flask response thread)
                ret_enc, jpeg_buf = cv2.imencode('.jpg', small, encode_params)
                
                with self.lock:
                    self.frame = small
                    if ret_enc:
                        self.jpeg_bytes = jpeg_buf.tobytes()
                        
            except Exception as e:
                logger.error(f"Camera frame error: {e}")
                time.sleep(0.5)

    def get_frame(self):
        """Returns the most recent frame for ML inference."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def get_jpeg_bytes(self):
        """Returns pre-encoded JPEG bytes for streaming (zero-copy path)."""
        with self.lock:
            return self.jpeg_bytes

    def get_mjpeg_frame(self, annotations=None):
        """Returns JPEG bytes with optional text overlay."""
        with self.lock:
            if self.frame is None:
                return None
            frame = self.frame.copy()

        # Draw annotations on a copy
        if annotations:
            y0, dy = 20, 22
            for i, text in enumerate(annotations):
                y = y0 + i * dy
                # Shadow for readability
                cv2.putText(frame, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                cv2.putText(frame, text, (7, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        return buffer.tobytes() if ret else None

    def switch_camera(self, new_index):
        """Hot-switch to a different camera index."""
        logger.info(f"Switching camera from index {self.camera_index} to {new_index}")
        self.stop()
        time.sleep(0.5)
        return self.start(camera_index=new_index)

    def get_available_cameras(self, max_check=5):
        """Probe which camera indices have devices."""
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
        time.sleep(0.3)
        if self.cap:
            self.cap.release()

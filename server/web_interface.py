from flask import Flask, render_template, Response, request, jsonify
from flask_cors import CORS
import logging
import threading
import time
import os
import glob

import config
from ml.training_pipeline import train_driving_model_in_background
from runtime_config import runtime_cfg, RuntimeConfig

logger = logging.getLogger(__name__)


class WebServer:
    """Flask server exposing API, Dashboard UI, and Configuration panel."""
    def __init__(self, shared_state):
        self.app = Flask(__name__, template_folder='templates')
        CORS(self.app)
        self.state = shared_state
        self.setup_routes()
        
    def setup_routes(self):
        # ─── Dashboard Page ───
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')

        # ─── Video Feed Stream ───
        @self.app.route('/video_feed')
        def video_feed():
            def generate_frames():
                while True:
                    if not self.state.camera:
                        time.sleep(0.5)
                        continue

                    # Fast path: use pre-encoded JPEG from camera thread
                    # Only use annotated path when there's something to show
                    need_annotations = (
                        self.state.mode != "manual" or
                        self.state.training_status == "training" or
                        self.state.bin_detected
                    )

                    if need_annotations:
                        annotations = [f"Mode: {self.state.mode.upper()}"]
                        if self.state.mode == "training":
                            annotations.append(f"Recording: {self.state.last_car_command}")
                            if self.state.data_recorder:
                                annotations.append(f"Frames: {self.state.data_recorder.counter}")
                        elif self.state.training_status == "training":
                            annotations.append(f"TRAINING: {self.state.training_progress}%")
                        elif self.state.mode == "autonomous":
                            if self.state.bin_detected:
                                annotations.append(f"BIN DETECTED ({self.state.bin_score:.2f})")
                            else:
                                annotations.append(f"Drive: {self.state.last_car_command}")
                        frame_bytes = self.state.camera.get_mjpeg_frame(annotations=annotations)
                    else:
                        # Zero-copy path — just grab the pre-encoded JPEG
                        frame_bytes = self.state.camera.get_jpeg_bytes()

                    if frame_bytes:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.1)  # ~10fps over WiFi — smooth enough, easy on Pi CPU
            return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
            
        # ─── Car Control ───
        @self.app.route('/control/car', methods=['POST'])
        def control_car():
            if self.state.mode == 'autonomous':
                return jsonify({"status": "error", "message": "Car is in autonomous mode"}), 400
                
            data = request.json
            action = data.get('action')
            speed = data.get('speed', config.DEFAULT_SPEED)
            
            if action in ['forward', 'backward', 'left', 'right', 'stop']:
                if self.state.motors:
                    self.state.motors.move(action, speed)
                self.state.last_car_command = action
                return jsonify({"status": "ok", "action": action})
            return jsonify({"status": "error", "message": "Invalid action"}), 400

        # ─── Arm Control ───
        @self.app.route('/control/arm', methods=['POST'])
        def control_arm():
            if self.state.mode == 'autonomous' and self.state.arm and self.state.arm.sequence_running:
                return jsonify({"status": "error", "message": "Arm is busy"}), 400
                
            data = request.json
            motor = data.get('motor')
            value = data.get('value')
            
            if motor and value is not None and self.state.arm:
                self.state.arm.execute_raw(motor, int(value))
                return jsonify({"status": "ok"})
            return jsonify({"status": "error", "message": "Invalid parameters or arm not connected"}), 400

        # ─── Arm Reset / Home Position ───
        @self.app.route('/control/arm/reset', methods=['POST'])
        def arm_reset():
            """Reset arm to home position — useful for calibration from dashboard."""
            if self.state.arm:
                self.state.arm.set_clamp(config.ARM_HOME_POSITION["clamp_angle"])
                return jsonify({"status": "ok", "message": "Arm reset to home position"})
            return jsonify({"status": "error", "message": "Arm not connected"}), 400

        # ─── Mode Control ───
        @self.app.route('/mode', methods=['POST'])
        def set_mode():
            data = request.json
            new_mode = data.get('mode')
            
            if new_mode not in ['manual', 'autonomous', 'training']:
                return jsonify({"status": "error", "message": "Invalid mode"}), 400

            # Handle transitions from Training
            if self.state.mode == 'training' and new_mode != 'training':
                if self.state.data_recorder:
                    self.state.data_recorder.stop()
                train_driving_model_in_background(self.state)

            # Handle transition to Training
            if new_mode == 'training':
                if self.state.data_recorder:
                    self.state.data_recorder.start()

            self.state.mode = new_mode
            
            if new_mode in ['manual', 'training']:
                if self.state.motors:
                    self.state.motors.stop()
                self.state.last_car_command = "stop"
                
            return jsonify({"status": "ok", "mode": new_mode})
            
        # ─── System Status ───
        @self.app.route('/status', methods=['GET'])
        def get_status():
            notif = ""
            if self.state.training_status == "done":
                notif = "Training complete! Model successfully compiled."
                self.state.training_status = "idle"
                
            serial_status = self.state.serial.get_status() if self.state.serial else {}
            
            return jsonify({
                "mode": self.state.mode,
                "car_connected": serial_status.get("car_connected", False),
                "arm_connected": serial_status.get("arm_connected", False),
                "car_port": serial_status.get("car_port", "N/A"),
                "arm_port": serial_status.get("arm_port", "N/A"),
                "camera_running": self.state.camera.running if self.state.camera else False,
                "camera_index": self.state.camera.camera_index if self.state.camera else -1,
                "training_status": self.state.training_status,
                "training_progress": self.state.training_progress,
                "notification": notif,
                "bin_detected": self.state.bin_detected,
                "arm_busy": self.state.arm.sequence_running if self.state.arm else False,
                "driving_model_loaded": self.state.dual_inference.driving_loaded if self.state.dual_inference else False,
                "bin_model_loaded": self.state.dual_inference.bin_loaded if self.state.dual_inference else False,
            })

        # ═══════════════════════════════════════════
        # SETTINGS / CONFIGURATION API
        # ═══════════════════════════════════════════

        @self.app.route('/settings', methods=['GET'])
        def get_settings():
            """Return all current runtime settings."""
            settings = runtime_cfg.get_all()
            # Add discovered ports for the dropdown
            settings["available_ports"] = RuntimeConfig.detect_serial_ports()
            # Add discovered cameras for the dropdown
            if self.state.camera:
                settings["available_cameras"] = self.state.camera.get_available_cameras()
            else:
                settings["available_cameras"] = [0]
            return jsonify(settings)

        @self.app.route('/settings', methods=['POST'])
        def update_settings():
            """Update runtime settings from the config dashboard."""
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400
            
            runtime_cfg.update(data)
            
            # Apply camera change immediately if camera_index changed
            if "camera_index" in data and self.state.camera:
                new_idx = int(data["camera_index"])
                if new_idx != self.state.camera.camera_index:
                    success = self.state.camera.switch_camera(new_idx)
                    if not success:
                        return jsonify({"status": "warning", 
                                        "message": f"Settings saved but camera {new_idx} failed to open"})
            
            # Apply serial port changes immediately
            if "car_serial_port" in data and self.state.serial:
                new_port = data["car_serial_port"]
                if new_port != "auto" and new_port != self.state.serial.car.port:
                    self.state.serial.car.change_port(new_port)
                    
            if "arm_serial_port" in data and self.state.serial:
                new_port = data["arm_serial_port"]
                if new_port != "auto" and new_port != self.state.serial.arm.port:
                    self.state.serial.arm.change_port(new_port)
            
            return jsonify({"status": "ok", "message": "Settings saved"})

        @self.app.route('/settings/reset', methods=['POST'])
        def reset_settings():
            """Reset all settings to factory defaults."""
            runtime_cfg.reset_to_defaults()
            return jsonify({"status": "ok", "message": "Settings reset to defaults"})

        @self.app.route('/settings/scan-ports', methods=['GET'])
        def scan_ports():
            """Scan for available serial ports."""
            return jsonify({"ports": RuntimeConfig.detect_serial_ports()})

        @self.app.route('/settings/scan-cameras', methods=['GET'])
        def scan_cameras():
            """Scan for available camera indices."""
            if self.state.camera:
                return jsonify({"cameras": self.state.camera.get_available_cameras()})
            return jsonify({"cameras": []})

        @self.app.route('/settings/test-camera', methods=['POST'])
        def test_camera():
            """Test a camera index without saving."""
            data = request.json
            idx = int(data.get("camera_index", 0))
            if self.state.camera:
                success = self.state.camera.switch_camera(idx)
                return jsonify({"status": "ok" if success else "error",
                                "message": f"Camera {idx} {'works' if success else 'failed'}"})
            return jsonify({"status": "error", "message": "Camera system not initialized"}), 400

        @self.app.route('/system/info', methods=['GET'])
        def system_info():
            """Return system information for the dashboard."""
            info = {
                "platform": config.PI_MODEL,
                "hotspot_ip": config.HOTSPOT_IP,
                "dashboard_port": config.FLASK_PORT,
                "ssid": runtime_cfg.get("hotspot_ssid", "GarbageBot"),
            }
            # Try to get system stats
            try:
                import psutil
                info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
                info["ram_percent"] = psutil.virtual_memory().percent
                info["cpu_temp"] = _get_cpu_temp()
            except ImportError:
                pass
            return jsonify(info)

    def run(self):
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        logger.info(f"Starting Web Server on {config.FLASK_HOST}:{config.FLASK_PORT}")
        self.app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, 
                     debug=False, use_reloader=False, threaded=True)

    def start_background(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()


def _get_cpu_temp():
    """Read CPU temperature from Pi thermal zone."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read().strip()) / 1000.0
            return round(temp, 1)
    except Exception:
        return None

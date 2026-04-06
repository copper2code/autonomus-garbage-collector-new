from flask import Flask, render_template, Response, request, jsonify
from flask_cors import CORS
import logging
import threading
import time

import config
from ml.training_pipeline import train_driving_model_in_background

logger = logging.getLogger(__name__)

class WebServer:
    """Flask server exposing API and Dashboard UI."""
    def __init__(self, shared_state):
        self.app = Flask(__name__, template_folder='templates')
        CORS(self.app)
        self.state = shared_state
        self.setup_routes()
        
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')

        @self.app.route('/video_feed')
        def video_feed():
            def generate_frames():
                while True:
                    annotations = [
                        f"Mode: {self.state.mode.upper()}",
                    ]

                    # Status Annotation overrides
                    if self.state.mode == "training":
                        annotations.append(f"Recording: {self.state.last_car_command}")
                        annotations.append(f"Frames: {self.state.data_recorder.counter}")
                    elif self.state.training_status == "training":
                        annotations.append(f"TRAINING IN PROGRESS: {self.state.training_progress}%")
                    elif self.state.training_status == "done":
                        annotations.append("TRAINING COMPLETE!")
                    elif self.state.mode == "autonomous":
                        if self.state.bin_detected:
                            annotations.append(f"BIN DETECTED ({self.state.bin_score:.2f})")
                            annotations.append("APPROACHING/COLLECTING...")
                        else:
                            annotations.append(f"Auto-Drive: {self.state.last_car_command}")
                    
                    frame_bytes = self.state.camera.get_mjpeg_frame(annotations=annotations)
                    if frame_bytes:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.05)  # Prevent CPU pegged at 100% on Raspberry Pi
            return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
            
        @self.app.route('/control/car', methods=['POST'])
        def control_car():
            if self.state.mode == 'autonomous':
                return jsonify({"status": "error", "message": "Car is in autonomous mode"}), 400
                
            data = request.json
            action = data.get('action')
            speed = data.get('speed', config.DEFAULT_SPEED)
            
            if action in ['forward', 'backward', 'left', 'right', 'stop']:
                self.state.motors.move(action, speed)
                self.state.last_car_command = action # Important for data recording mapping
                return jsonify({"status": "ok", "action": action})
            return jsonify({"status": "error", "message": "Invalid action"}), 400

        @self.app.route('/control/arm', methods=['POST'])
        def control_arm():
            if self.state.mode == 'autonomous' and self.state.arm.sequence_running:
                return jsonify({"status": "error", "message": "Arm is busy"}), 400
                
            data = request.json
            motor = data.get('motor')
            value = data.get('value')
            
            if motor and value is not None:
                self.state.arm.execute_raw(motor, int(value))
                return jsonify({"status": "ok"})
            return jsonify({"status": "error", "message": "Invalid parameters"}), 400

        @self.app.route('/mode', methods=['POST'])
        def set_mode():
            data = request.json
            new_mode = data.get('mode')
            
            if new_mode not in ['manual', 'autonomous', 'training']:
                return jsonify({"status": "error", "message": "Invalid mode"}), 400

            # Handle transitions from Training
            if self.state.mode == 'training' and new_mode != 'training':
                self.state.data_recorder.stop()
                # Trigger background training
                train_driving_model_in_background(self.state)

            # Handle transition to Training
            if new_mode == 'training':
                self.state.data_recorder.start()

            self.state.mode = new_mode
            
            if new_mode in ['manual', 'training']:
                self.state.motors.stop()
                self.state.last_car_command = "stop"
                
            return jsonify({"status": "ok", "mode": new_mode})
            
        @self.app.route('/status', methods=['GET'])
        def get_status():
            # Clear notification if it was shown to UI
            notif = ""
            if self.state.training_status == "done":
                notif = "Training complete! Model successfully compiled."
                self.state.training_status = "idle" # reset
                
            return jsonify({
                "mode": self.state.mode,
                "car_connected": self.state.serial.car.connected,
                "arm_connected": self.state.serial.arm.connected,
                "training_status": self.state.training_status,
                "training_progress": self.state.training_progress,
                "notification": notif,
                "bin_detected": self.state.bin_detected,
                "arm_busy": self.state.arm.sequence_running
            })

    def run(self):
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        logger.info(f"Starting Web Server on {config.FLASK_HOST}:{config.FLASK_PORT}")
        self.app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False, use_reloader=False)

    def start_background(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()

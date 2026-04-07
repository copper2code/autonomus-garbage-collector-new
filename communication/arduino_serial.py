import serial
import json
import time
import threading
import logging
import glob

import config

logger = logging.getLogger(__name__)


class ArduinoSerial:
    """Manages a serial connection to a single Arduino with auto-reconnect."""
    def __init__(self, port, baud_rate, timeout=1.0, name="Arduino"):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.name = name
        self.serial = None
        self.connected = False
        self.lock = threading.Lock()
        
        self.connect()

    def connect(self):
        with self.lock:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()
                self.serial = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
                self.connected = True
                logger.info(f"✓ Connected to {self.name} on {self.port}")
                time.sleep(2)  # Wait for Arduino to reset after serial connection
            except serial.SerialException as e:
                self.connected = False
                logger.warning(f"✗ Could not connect to {self.name} on {self.port}: {e}")
            except OSError as e:
                self.connected = False
                logger.warning(f"✗ Port {self.port} does not exist for {self.name}: {e}")

    def send_json(self, data: dict):
        if not self.connected:
            logger.debug(f"Not connected to {self.name} ({self.port}), dropping: {data}")
            return False
            
        try:
            msg = json.dumps(data) + "\n"
            with self.lock:
                self.serial.write(msg.encode('utf-8'))
                return True
        except (serial.SerialException, OSError) as e:
            logger.error(f"Error writing to {self.name} ({self.port}): {e}")
            self.connected = False
            self._start_reconnect_thread()
            return False

    def read_line(self, timeout=1.0):
        """Read a single line from serial with timeout."""
        if not self.connected:
            return None
        try:
            with self.lock:
                old_timeout = self.serial.timeout
                self.serial.timeout = timeout
                line = self.serial.readline().decode('utf-8').strip()
                self.serial.timeout = old_timeout
                return line if line else None
        except Exception:
            return None

    def flush_input(self):
        """Flush the input buffer."""
        if self.connected:
            try:
                with self.lock:
                    self.serial.reset_input_buffer()
            except Exception:
                pass
            
    def _start_reconnect_thread(self):
        def reconnect_worker():
            while not self.connected:
                logger.info(f"Attempting reconnection to {self.name} ({self.port})...")
                self.connect()
                if not self.connected:
                    time.sleep(config.SERIAL_RECONNECT_DELAY)
        
        t = threading.Thread(target=reconnect_worker, daemon=True)
        t.start()

    def change_port(self, new_port):
        """Change the port and reconnect (called from config dashboard)."""
        logger.info(f"Changing {self.name} port from {self.port} to {new_port}")
        self.close()
        self.port = new_port
        self.connect()

    def close(self):
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.close()
                self.connected = False


def discover_serial_ports():
    """Find all available serial ports that could be Arduinos."""
    patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/arduino_*"]
    ports = []
    for pattern in patterns:
        ports.extend(glob.glob(pattern))
    ports.sort()
    return ports


def identify_arduino(port, baud_rate=115200, timeout=4.0):
    """
    Listen to a serial port for an Arduino identity broadcast.
    
    Each Arduino continuously sends {"id":"car"} or {"id":"arm"} until acked.
    We listen for up to `timeout` seconds, then send {"cmd":"ack"} to confirm.
    
    Returns: "car", "arm", or None if identification failed.
    """
    try:
        ser = serial.Serial(port, baud_rate, timeout=1.0)
        time.sleep(2)  # Wait for Arduino reset after connection
        ser.reset_input_buffer()  # Clear any boot garbage
        
        identity = None
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            try:
                line = ser.readline().decode('utf-8').strip()
                if not line:
                    continue
                    
                data = json.loads(line)
                if "id" in data:
                    identity = data["id"]
                    logger.info(f"🔍 Port {port} identifies as: {identity.upper()}")
                    
                    # Send acknowledgment
                    ack = json.dumps({"cmd": "ack"}) + "\n"
                    ser.write(ack.encode('utf-8'))
                    time.sleep(0.3)
                    
                    # Read the confirmation
                    confirm = ser.readline().decode('utf-8').strip()
                    if confirm:
                        logger.info(f"✓ {identity.upper()} Arduino confirmed on {port}")
                    
                    ser.close()
                    return identity
                    
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # Skip garbage data during boot
        
        ser.close()
        logger.warning(f"⚠ Port {port}: no identification received within {timeout}s")
        return None
        
    except serial.SerialException as e:
        logger.warning(f"✗ Could not open {port} for identification: {e}")
        return None
    except OSError as e:
        logger.warning(f"✗ Port {port} error: {e}")
        return None


class SerialManager:
    """
    Manages connections to both Arduinos with auto-identification.
    
    Flow:
    1. Scan all serial ports (/dev/ttyUSB*, /dev/ttyACM*)
    2. Listen to each for identity broadcasts ("car" / "arm")
    3. Send ack to confirm
    4. Assign to self.car / self.arm
    """
    def __init__(self):
        logger.info("━━━ Initializing Serial Manager ━━━")
        
        self.car = None
        self.arm = None

        # Check if user has manually set ports in runtime config
        try:
            from runtime_config import runtime_cfg
            car_port = runtime_cfg.get("car_serial_port", "auto")
            arm_port = runtime_cfg.get("arm_serial_port", "auto")
        except ImportError:
            car_port = "auto"
            arm_port = "auto"

        # ── Manual port assignment (user set specific ports in Settings) ──
        if car_port != "auto" and arm_port != "auto":
            logger.info(f"Using manually configured ports: car={car_port}, arm={arm_port}")
            self.car = ArduinoSerial(car_port, config.SERIAL_BAUD_RATE, config.SERIAL_TIMEOUT, name="Car Arduino")
            self.arm = ArduinoSerial(arm_port, config.SERIAL_BAUD_RATE, config.SERIAL_TIMEOUT, name="Arm Arduino")
            # Still send ack to let Arduinos know they're recognized
            self._send_ack(self.car)
            self._send_ack(self.arm)
            return

        # ── Auto-identification: listen for Arduino identity broadcasts ──
        logger.info("🔍 Auto-detecting Arduinos (listening for identity broadcasts)...")
        
        available_ports = discover_serial_ports()
        if not available_ports:
            logger.warning("⚠ No serial ports found. Connect Arduinos via USB.")
            self._create_dummy_connections()
            return
        
        logger.info(f"Found serial ports: {available_ports}")
        
        identified = {}  # {"car": "/dev/ttyUSB0", "arm": "/dev/ttyUSB1"}
        
        for port in available_ports:
            identity = identify_arduino(port, config.SERIAL_BAUD_RATE)
            if identity in ("car", "arm"):
                identified[identity] = port
            
            # Stop scanning if we found both
            if "car" in identified and "arm" in identified:
                break
        
        # Assign connections based on identification
        if "car" in identified:
            self.car = ArduinoSerial(identified["car"], config.SERIAL_BAUD_RATE, 
                                     config.SERIAL_TIMEOUT, name="Car Arduino")
            # Re-send ack since ArduinoSerial reconnected (Arduino resets on serial open)
            time.sleep(2)
            self._wait_and_ack(self.car, "car")
        else:
            logger.warning("⚠ Car Arduino not found — driving disabled")
            
        if "arm" in identified:
            self.arm = ArduinoSerial(identified["arm"], config.SERIAL_BAUD_RATE,
                                     config.SERIAL_TIMEOUT, name="Arm Arduino")
            time.sleep(2)
            self._wait_and_ack(self.arm, "arm")
        else:
            logger.warning("⚠ Arm Arduino not found — arm control disabled")

        # Create dummy connections for missing Arduinos (so rest of code doesn't crash)
        if self.car is None:
            self.car = DummySerial("Car Arduino")
        if self.arm is None:
            self.arm = DummySerial("Arm Arduino")

        # Log summary
        logger.info("━━━ Serial Discovery Complete ━━━")
        logger.info(f"  Car: {self.car.port if hasattr(self.car, 'port') else 'NOT FOUND'} "
                     f"({'✓ Connected' if self.car.connected else '✗ Disconnected'})")
        logger.info(f"  Arm: {self.arm.port if hasattr(self.arm, 'port') else 'NOT FOUND'} "
                     f"({'✓ Connected' if self.arm.connected else '✗ Disconnected'})")

    def _send_ack(self, arduino):
        """Send acknowledgment to an Arduino."""
        if arduino and arduino.connected:
            arduino.send_json({"cmd": "ack"})
            time.sleep(0.3)

    def _wait_and_ack(self, arduino, expected_id, timeout=5.0):
        """Wait for Arduino to start screaming its identity after reset, then ack it."""
        if not arduino or not arduino.connected:
            return False
        
        arduino.flush_input()
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            line = arduino.read_line(timeout=1.0)
            if line:
                try:
                    data = json.loads(line)
                    if data.get("id") == expected_id:
                        arduino.send_json({"cmd": "ack"})
                        time.sleep(0.3)
                        # Read confirmation
                        arduino.read_line(timeout=1.0)
                        logger.info(f"✓ {expected_id.upper()} Arduino acknowledged on {arduino.port}")
                        return True
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        
        logger.warning(f"⚠ Could not acknowledge {expected_id} Arduino (may already be identified)")
        # Send ack anyway in case it's waiting
        arduino.send_json({"cmd": "ack"})
        return False

    def _create_dummy_connections(self):
        """Create dummy serial objects so the rest of the code doesn't crash."""
        if self.car is None:
            self.car = DummySerial("Car Arduino")
        if self.arm is None:
            self.arm = DummySerial("Arm Arduino")

    def close_all(self):
        if self.car:
            self.car.close()
        if self.arm:
            self.arm.close()
        
    def get_status(self):
        """Return connection status dict for the dashboard."""
        return {
            "car_port": getattr(self.car, 'port', 'N/A'),
            "car_connected": getattr(self.car, 'connected', False),
            "arm_port": getattr(self.arm, 'port', 'N/A'),
            "arm_connected": getattr(self.arm, 'connected', False),
        }


class DummySerial:
    """Placeholder when an Arduino is not connected. Prevents crashes in rest of code."""
    def __init__(self, name="Unknown"):
        self.name = name
        self.port = "N/A"
        self.connected = False
    
    def send_json(self, data):
        return False
    
    def read_line(self, timeout=1.0):
        return None
    
    def flush_input(self):
        pass
    
    def change_port(self, new_port):
        pass
    
    def close(self):
        pass

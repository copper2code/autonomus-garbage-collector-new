import serial
import json
import time
import threading
import logging

import config

logger = logging.getLogger(__name__)

class ArduinoSerial:
    """Manages a serial connection to a single Arduino with auto-reconnect."""
    def __init__(self, port, baud_rate, timeout=1.0):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
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
                logger.info(f"Connected to Arduino on {self.port}")
                time.sleep(2)  # Wait for Arduino to reset after serial connection
            except serial.SerialException as e:
                self.connected = False
                logger.error(f"Failed to connect to {self.port}: {e}")

    def send_json(self, data: dict):
        if not self.connected:
            logger.warning(f"Not connected to {self.port}, dropping command: {data}")
            return False
            
        try:
            msg = json.dumps(data) + "\n"
            with self.lock:
                self.serial.write(msg.encode('utf-8'))
                # Optional: Read response
                # response = self.serial.readline().decode('utf-8').strip()
                # return response
                return True
        except serial.SerialException as e:
            logger.error(f"Error writing to {self.port}: {e}")
            self.connected = False
            self._start_reconnect_thread()
            return False
            
    def _start_reconnect_thread(self):
        def reconnect_worker():
            while not self.connected:
                logger.info(f"Attempting reconnection to {self.port}...")
                self.connect()
                if not self.connected:
                    time.sleep(config.SERIAL_RECONNECT_DELAY)
        
        t = threading.Thread(target=reconnect_worker, daemon=True)
        t.start()

    def close(self):
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.close()
                self.connected = False


class SerialManager:
    """Manages connections to all Arduinos."""
    def __init__(self):
        logger.info("Initializing Serial Manager...")
        self.car = ArduinoSerial(config.CAR_SERIAL_PORT, config.SERIAL_BAUD_RATE, config.SERIAL_TIMEOUT)
        self.arm = ArduinoSerial(config.ARM_SERIAL_PORT, config.SERIAL_BAUD_RATE, config.SERIAL_TIMEOUT)

    def close_all(self):
        self.car.close()
        self.arm.close()

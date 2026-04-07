"""
runtime_config.py — Persistent runtime configuration manager.

Stores user-configurable settings in a JSON file so they survive reboots.
Falls back to defaults from config.py when no user override exists.
Accessible from the web dashboard — no SSH needed.
"""

import os
import json
import logging
import glob

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_settings.json")

# Defaults — these mirror config.py but are the user-tunable subset
DEFAULTS = {
    "camera_index": 0,
    "camera_width": 640,
    "camera_height": 480,
    "camera_fps": 15,
    "car_serial_port": "auto",      # "auto" = scan for Arduino
    "arm_serial_port": "auto",
    "default_speed": 180,
    "turn_speed": 160,
    "bin_detect_threshold": 0.85,
    "hotspot_ssid": "GarbageBot",
    "hotspot_password": "robot1234",
    "hotspot_enabled": True,
    "stream_width": 320,
    "stream_height": 240,
}


class RuntimeConfig:
    """Manages user-configurable settings with JSON persistence."""

    def __init__(self):
        self._settings = dict(DEFAULTS)
        self.load()

    def load(self):
        """Load settings from JSON file, merging with defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                self._settings.update(saved)
                logger.info(f"Loaded user settings from {CONFIG_FILE}")
            except Exception as e:
                logger.warning(f"Failed to load settings, using defaults: {e}")
        else:
            logger.info("No saved settings found, using defaults.")
            self.save()  # Create the file with defaults

    def save(self):
        """Persist current settings to JSON file."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._settings, f, indent=2)
            logger.info(f"Settings saved to {CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value

    def get_all(self):
        return dict(self._settings)

    def update(self, updates: dict):
        """Update multiple settings at once."""
        for key, value in updates.items():
            if key in DEFAULTS:  # Only allow known keys
                # Type-cast to match defaults
                expected_type = type(DEFAULTS[key])
                try:
                    if expected_type == bool:
                        if isinstance(value, str):
                            value = value.lower() in ("true", "1", "yes")
                        else:
                            value = bool(value)
                    elif expected_type == int:
                        value = int(value)
                    elif expected_type == float:
                        value = float(value)
                    else:
                        value = str(value)
                    self._settings[key] = value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid value for {key}: {value} ({e})")
            else:
                logger.warning(f"Ignoring unknown setting key: {key}")
        self.save()

    def reset_to_defaults(self):
        """Reset all settings to factory defaults."""
        self._settings = dict(DEFAULTS)
        self.save()
        logger.info("Settings reset to defaults.")

    @staticmethod
    def detect_serial_ports():
        """Auto-detect Arduino serial ports on the Pi."""
        patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/arduino_*"]
        ports = []
        for pattern in patterns:
            ports.extend(glob.glob(pattern))
        ports.sort()
        return ports


# Singleton instance
runtime_cfg = RuntimeConfig()

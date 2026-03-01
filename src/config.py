import os
import json
import numpy as np

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

SOUND_FILE = os.path.join(ASSETS_DIR, "alert_sound.mp3")
LOG_FILE = os.path.join(LOGS_DIR, "black_box.csv")

# --- Default Configuration ---
# These values will be overwritten if config.json exists
_DEFAULTS = {
    "system": {
        "camera_index": 0,
        "calibration_frames": 60,
        "fps_limit": 30
    },
    "hardware": {
        "enabled": True,
        "port": "COM3",
        "baud_rate": 9600,
        "timeout": 3,
        "heartbeat_interval": 0.5
    },
    "thresholds": {
        "ear_closed": 0.20,
        "mar_yawn": 0.50,
        "pitch_down": -15.0,
        "fusion_warning": 0.40,
        "fusion_critical": 0.70
    },
    "weights": {
        "perclos": 0.50,
        "mouth": 0.20,
        "head": 0.20,
        "microsleep": 0.30
    },
    "logging": {
        "enabled": True,
        "file_path": "logs/session_data.csv"
    }
}

# --- Load Configuration ---
def load_config():
    config = _DEFAULTS.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
                # Deep update for nested dictionaries
                for section, settings in user_config.items():
                    if section in config:
                        config[section].update(settings)
        except Exception as e:
            print(f"Error loading config.json: {e}. Using defaults.")
    return config

_CONFIG = load_config()

# --- Hardware Configuration ---
CAMERA_INDEX = _CONFIG["system"]["camera_index"]
ARDUINO_PORT = _CONFIG["hardware"]["port"]
ARDUINO_BAUD_RATE = _CONFIG["hardware"]["baud_rate"]
ARDUINO_TIMEOUT = _CONFIG["hardware"]["timeout"]
HEARTBEAT_INTERVAL = _CONFIG["hardware"]["heartbeat_interval"]
HARDWARE_ENABLED = _CONFIG["hardware"]["enabled"]

# --- Vision Engine (MediaPipe) ---
MP_MIN_DETECTION_CONFIDENCE = 0.5
MP_MIN_TRACKING_CONFIDENCE = 0.5

# --- Fatigue Logic (PERCLOS & Fusion) ---
W_PERCLOS = _CONFIG["weights"]["perclos"]
W_MOUTH = _CONFIG["weights"]["mouth"]
W_HEAD = _CONFIG["weights"]["head"]
W_MICROSLEEP = _CONFIG["weights"]["microsleep"]

# Fusion Thresholds
FUSION_WARNING_THRESHOLD = _CONFIG["thresholds"]["fusion_warning"]
FUSION_CRITICAL_THRESHOLD = _CONFIG["thresholds"].get("fusion_critical", 0.70)

# Eye Aspect Ratio (EAR) Threshold
EAR_THRESHOLD = _CONFIG["thresholds"]["ear_closed"]
# Mouth Aspect Ratio (MAR) Threshold
MAR_THRESHOLD = _CONFIG["thresholds"]["mar_yawn"]

# Time Windows
PERCLOS_WINDOW_SIZE = 60.0  
MICRO_SLEEP_THRESHOLD = 1.0 
YAWN_TIME_THRESHOLD = 2.0   

# Auto-Braking Safety
ALERT_TIMEOUT = 4.0   

# --- Head Pose ---
HEAD_PITCH_THRESHOLD = 25.0
HEAD_YAW_THRESHOLD = 30.0
DROWSY_PITCH_THRESHOLD = _CONFIG["thresholds"]["pitch_down"]
DROWSY_HEAD_DURATION = 1.5

# --- Calibration ---
CALIBRATION_FRAMES = _CONFIG["system"]["calibration_frames"]

# --- HUD Settings ---
GRAPH_HEIGHT = 100
GRAPH_WIDTH = 300
GRAPH_BUFFER_SIZE = 150 
HUD_COLOR_SAFE = (0, 255, 0)
HUD_COLOR_WARN = (0, 255, 255)
HUD_COLOR_CRIT = (0, 0, 255)

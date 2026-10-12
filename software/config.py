"""
Global Configuration for Dual-Glove ASL Translator with N-Atlas
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GESTURES_DIR = DATA_DIR / "gestures"
MODELS_DIR = DATA_DIR / "models"
CALIBRATION_DIR = DATA_DIR / "calibration"

for d in [DATA_DIR, GESTURES_DIR, MODELS_DIR, CALIBRATION_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DATASET_CSV_PATH = GESTURES_DIR / "asl_dual_glove_dataset.csv"
MODEL_PATH = MODELS_DIR / "asl_classifier.joblib"
SCALER_PATH = MODELS_DIR / "feature_scaler.joblib"
LABEL_ENCODER_PATH = MODELS_DIR / "label_encoder.joblib"
MODEL_METADATA_PATH = MODELS_DIR / "model_metadata.json"
CALIBRATION_JSON_PATH = CALIBRATION_DIR / "glove_calibration.json"

# Network & Telemetry Settings
DEFAULT_UDP_HOST = "0.0.0.0"      # Listen on all local network adapters
DEFAULT_UDP_PORT = 5005
UDP_BUFFER_SIZE = 2048
TELEMETRY_TIMEOUT_SEC = 2.0       # Mark glove as disconnected if no packet received

# Sensor Feature Column Names (1-Hand and 2-Hands modes)
LEFT_FEATURE_COLUMNS = [
    "L_Flex_Thumb", "L_Flex_Index", "L_Flex_Middle", "L_Flex_Ring", "L_Flex_Pinky",
    "L_Accel_X", "L_Accel_Y", "L_Accel_Z",
    "L_Gyro_X", "L_Gyro_Y", "L_Gyro_Z",
    "L_Mag_X", "L_Mag_Y", "L_Mag_Z"
]

RIGHT_FEATURE_COLUMNS = [
    "R_Flex_Thumb", "R_Flex_Index", "R_Flex_Middle", "R_Flex_Ring", "R_Flex_Pinky",
    "R_Accel_X", "R_Accel_Y", "R_Accel_Z",
    "R_Gyro_X", "R_Gyro_Y", "R_Gyro_Z",
    "R_Mag_X", "R_Mag_Y", "R_Mag_Z"
]

# Dual Glove (28 features total: 14 per hand)
DUAL_FEATURE_COLUMNS = LEFT_FEATURE_COLUMNS + RIGHT_FEATURE_COLUMNS
FEATURE_COLUMNS = DUAL_FEATURE_COLUMNS

# Gesture Catalog (Letters, numbers, greetings, and two-handed everyday phrases)
DEFAULT_GESTURES = [
    # Neutral Rest State
    "IDLE",
    # Basic Alphabet
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z",
    # High-Frequency Signs / Everyday Words
    "HELLO",
    "THANK_YOU",
    "PLEASE",
    "YES",
    "NO",
    "HELP",
    "WATER",
    "FOOD",
    "DOCTOR",
    "FAMILY",
    "HOW_ARE_YOU",
    "I_LOVE_YOU",
    "GOOD_MORNING",
    "PEACE",
    "GOODBYE"
]

# Static Poses (Handshape held steady in space: Alphabets A-Y, Numbers, Rest)
STATIC_GESTURES = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N",
    "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "IDLE", "PEACE"
]

# Dynamic Gestures (Motion trajectory over time: Greetings, Conversational Words, J, Z)
DYNAMIC_GESTURES = [
    "J", "Z", "HELLO", "THANK_YOU", "PLEASE", "YES", "NO", "HELP",
    "WATER", "FOOD", "DOCTOR", "FAMILY", "HOW_ARE_YOU", "I_LOVE_YOU",
    "GOOD_MORNING", "GOODBYE"
]

# Nigerian Translation Languages Supported
SUPPORTED_LANGUAGES = {
    "English": {"code": "en", "nllb_code": "eng_Latn", "name": "English"},
    "Yoruba":  {"code": "yo", "nllb_code": "yor_Latn", "name": "Yorùbá (Nigeria)"},
    "Igbo":    {"code": "ig", "nllb_code": "ibo_Latn", "name": "Igbo (Nigeria)"},
    "Hausa":   {"code": "ha", "nllb_code": "hau_Latn", "name": "Hausa (Nigeria)"}
}

# Machine Learning Parameters
CONFIDENCE_THRESHOLD = 0.75       # Min probability required to trigger gesture
STABILITY_FRAMES = 6              # Consecutive frames required to confirm gesture (~120ms)
DEBOUNCE_COOLDOWN_SEC = 1.0       # Cooldown before the same sign can trigger again

# Static Pose Burst & Spatial Invariance Settings
DEFAULT_STATIC_SNAPSHOTS = 50       # Recommended minimum snapshots for static poses
DEFAULT_BURST_DURATION_SEC = 2.5    # Capture duration for 50+ snapshot burst
SPATIAL_AUGMENTATION_DEFAULT = True # Enable synthetic 3D spatial translation invariance

# N-Atlas HuggingFace Model Configuration
NATLAS_MODEL_NAME = "facebook/nllb-200-distilled-600M" # Compatible Afro-centric multilingual model
USE_NEURAL_TRANSLATION_DEFAULT = False  # Start with ultra-fast offline dictionary, toggle to neural


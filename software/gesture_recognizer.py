"""
Real-Time Gesture Recognizer
Performs live classification on synchronized dual-glove feature streams with confidence
thresholding, consecutive frame stability gating, and debouncing.
"""
import json
import time
import logging
from typing import Optional, Tuple, Dict, Any
import numpy as np
import joblib
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GestureRecognizer")

class GestureRecognizer:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.is_loaded = False

        # Model configuration
        self.hand_mode: str = "dual"  # "right", "left", or "dual"
        self.expected_features: int = 28
        self.feature_columns: list = config.DUAL_FEATURE_COLUMNS

        # Stability and Single-Shot Latch State Machine (Zero Word Repetition)
        self.candidate_label: Optional[str] = None
        self.candidate_count: int = 0
        self.latched_gesture: Optional[str] = None
        self.last_confirmed_gesture: Optional[str] = None
        self.last_trigger_time: float = 0.0
        self.idle_frames: int = 0

        self.load_model()

    def load_model(self) -> bool:
        """Load trained model, scaler, label encoder, and metadata from disk."""
        if not (config.MODEL_PATH.exists() and config.SCALER_PATH.exists() and config.LABEL_ENCODER_PATH.exists()):
            self.is_loaded = False
            return False

        try:
            self.model = joblib.load(config.MODEL_PATH)
            self.scaler = joblib.load(config.SCALER_PATH)
            self.label_encoder = joblib.load(config.LABEL_ENCODER_PATH)

            # Read metadata if present
            if hasattr(config, "MODEL_METADATA_PATH") and config.MODEL_METADATA_PATH.exists():
                try:
                    with open(config.MODEL_METADATA_PATH, "r") as f:
                        meta = json.load(f)
                    self.hand_mode = meta.get("hand_mode", "dual")
                    self.expected_features = meta.get("num_features", 28)
                    self.feature_columns = meta.get("feature_columns", config.DUAL_FEATURE_COLUMNS)
                except Exception as me:
                    logger.warning(f"Could not read metadata JSON: {me}")
            else:
                # Infer feature count from scaler
                n_feat = getattr(self.scaler, "n_features_in_", 28)
                self.expected_features = n_feat
                if n_feat == 14:
                    self.hand_mode = "right"
                    self.feature_columns = config.RIGHT_FEATURE_COLUMNS
                else:
                    self.hand_mode = "dual"
                    self.feature_columns = config.DUAL_FEATURE_COLUMNS

            self.is_loaded = True
            logger.info(
                f"GestureRecognizer model loaded. Hand Mode: '{self.hand_mode}' ({self.expected_features} features). "
                f"Classes ({len(self.label_encoder.classes_)}): {list(self.label_encoder.classes_)}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load model artifacts: {e}")
            self.is_loaded = False
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Return metadata summary about active model."""
        if not self.is_loaded:
            return {"loaded": False, "hand_mode": "None", "num_features": 0, "classes": []}
        return {
            "loaded": True,
            "hand_mode": self.hand_mode,
            "num_features": self.expected_features,
            "classes": list(self.label_encoder.classes_) if self.label_encoder else []
        }

    def predict_frame(self, feature_vector: np.ndarray) -> Tuple[Optional[str], float, Dict[str, float]]:
        """
        Predict single frame, automatically adapting to 1-hand (14 feat) or 2-hands (28 feat).
        Returns:
            (best_label, confidence, top_probabilities_dict)
        """
        if not self.is_loaded:
            return None, 0.0, {}

        try:
            vec = np.array(feature_vector, dtype=float).ravel()
            n_in = getattr(self.scaler, "n_features_in_", self.expected_features)

            # Feature vector dimension adaptation
            if len(vec) == 28 and n_in == 14:
                # Incoming is dual-hand vector, but model was trained on single-hand
                if self.hand_mode == "left":
                    vec = vec[0:14]
                else:  # "right" or default
                    vec = vec[14:28]
            elif len(vec) == 14 and n_in == 28:
                # Model requires dual hands, but only single hand vector provided
                return None, 0.0, {}
            elif len(vec) != n_in:
                if len(vec) < n_in:
                    vec = np.pad(vec, (0, n_in - len(vec)), "constant")
                else:
                    vec = vec[:n_in]

            vec_reshaped = vec.reshape(1, -1)
            vec_scaled = self.scaler.transform(vec_reshaped)

            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(vec_scaled)[0]
                best_idx = int(np.argmax(probs))
                confidence = float(probs[best_idx])
                best_label = self.label_encoder.inverse_transform([best_idx])[0]

                # Extract top 3 candidates for diagnostics
                top_indices = np.argsort(probs)[::-1][:3]
                top_dict = {
                    self.label_encoder.inverse_transform([idx])[0]: float(probs[idx])
                    for idx in top_indices
                }
                return best_label, confidence, top_dict
            else:
                pred = self.model.predict(vec_scaled)[0]
                label = self.label_encoder.inverse_transform([pred])[0]
                return label, 1.0, {label: 1.0}

        except Exception as e:
            logger.debug(f"Inference error: {e}")
            return None, 0.0, {}

    def process_live_stream(
        self,
        feature_vector: np.ndarray,
        motion_metrics: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], float, bool, Dict[str, Any]]:
        """
        Process incoming live telemetry frame with kinematic motion awareness
        and Single-Shot Latch & Release state machine to eliminate word repetition.
        
        Args:
            feature_vector: 14-dim or 28-dim normalized sensor reading.
            motion_metrics: Optional dict from receiver.get_motion_metrics() containing
                            angular_velocity_dps, is_moving, motion_category.
                            
        Returns:
            (label, confidence, is_new_event, metadata_dict)
        """
        is_moving = motion_metrics.get("is_moving", False) if motion_metrics else False
        omega = motion_metrics.get("angular_velocity_dps", 0.0) if motion_metrics else 0.0
        motion_state_desc = "IN MOTION 🔄" if is_moving else "STEADY POSE ✋"

        label, conf, top_dict = self.predict_frame(feature_vector)

        # 1. Below Confidence Threshold: Hand is transitioning or relaxed
        if label is None or conf < config.CONFIDENCE_THRESHOLD:
            self.idle_frames += 1
            if self.idle_frames >= 3:
                # Release latch after 3 consecutive neutral/uncertain frames (~60ms)
                self.latched_gesture = None
                self.candidate_label = None
                self.candidate_count = 0
            meta = {
                "gesture_type": "NONE",
                "is_dynamic": False,
                "motion_state": motion_state_desc,
                "is_latched": False,
                "velocity_dps": omega,
                "top_candidates": top_dict
            }
            return None, conf if conf is not None else 0.0, False, meta

        # 2. Neutral Rest / Idle States
        if label in ["IDLE", "REST"]:
            self.idle_frames += 1
            if self.idle_frames >= 2:
                self.latched_gesture = None
                self.candidate_label = None
                self.candidate_count = 0
            meta = {
                "gesture_type": "NEUTRAL REST",
                "is_dynamic": False,
                "motion_state": motion_state_desc,
                "is_latched": False,
                "velocity_dps": omega,
                "top_candidates": top_dict
            }
            return label, conf, False, meta

        # 3. Active Recognized Sign: Classify Static vs. Dynamic
        self.idle_frames = 0
        is_dynamic_sign = label in config.DYNAMIC_GESTURES
        gesture_type_desc = "DYNAMIC GESTURE 🔄" if is_dynamic_sign else "STATIC POSE ✋"

        # Stability counter
        if label == self.candidate_label:
            self.candidate_count += 1
        else:
            self.candidate_label = label
            self.candidate_count = 1

        is_new_event = False
        req_frames = config.STABILITY_FRAMES

        # Confirmation condition:
        if self.candidate_count >= req_frames:
            # Check Latch:
            # If the sign is already latched, user is simply holding the pose.
            # ZERO REPETITION: Do NOT trigger again!
            if label == self.latched_gesture:
                is_new_event = False
            else:
                # Fresh, unlatched sign confirmation!
                self.latched_gesture = label
                self.last_confirmed_gesture = label
                self.last_trigger_time = time.time()
                is_new_event = True
                logger.info(
                    f"Gesture Triggered: '{label}' ({gesture_type_desc}) | Conf: {conf*100:.1f}% | "
                    f"Omega: {omega:.1f}°/s [Latched to prevent repetition]"
                )

        meta = {
            "gesture_type": gesture_type_desc,
            "is_dynamic": is_dynamic_sign,
            "motion_state": motion_state_desc,
            "is_latched": (label == self.latched_gesture),
            "velocity_dps": omega,
            "top_candidates": top_dict
        }

        return label, conf, is_new_event, meta

    def reset_state(self):
        """Reset temporal state filters and unlatch."""
        self.candidate_label = None
        self.candidate_count = 0
        self.latched_gesture = None
        self.last_confirmed_gesture = None
        self.last_trigger_time = 0.0
        self.idle_frames = 0

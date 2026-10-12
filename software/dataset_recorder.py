"""
Dataset Recorder Module
Captures, labels, and manages dual-glove sensory dataset samples for ASL recognition model training.
"""
import time
import threading
import logging
from typing import Dict, Optional, Callable, Any, List, Tuple
import pandas as pd
import numpy as np
import config
from receiver import DualGloveReceiver

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DatasetRecorder")

class DatasetRecorder:
    def __init__(self, receiver: DualGloveReceiver):
        self.receiver = receiver
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None

    def append_single_frame(self, label: str, feature_vector: np.ndarray, hand_mode: str = "both") -> bool:
        """Append an instantaneous 14-D or 28-D vector to the dataset CSV."""
        mode_lower = str(hand_mode).lower().strip()
        if len(feature_vector) == len(config.RIGHT_FEATURE_COLUMNS) or mode_lower in ["right", "one_hand_right", "1-hand (right)"]:
            cols = config.RIGHT_FEATURE_COLUMNS
            actual_mode = "RIGHT"
        elif len(feature_vector) == len(config.LEFT_FEATURE_COLUMNS) or mode_lower in ["left", "one_hand_left", "1-hand (left)"]:
            cols = config.LEFT_FEATURE_COLUMNS
            actual_mode = "LEFT"
        else:
            cols = config.DUAL_FEATURE_COLUMNS
            actual_mode = "DUAL"

        if len(feature_vector) != len(cols):
            logger.error(f"Vector size mismatch: expected {len(cols)}, got {len(feature_vector)}")
            return False

        row = {
            "timestamp": time.time(),
            "label": label.strip().upper(),
            "hand_mode": actual_mode,
            **{col: float(val) for col, val in zip(cols, feature_vector)}
        }
        df = pd.DataFrame([row])
        header = not config.DATASET_CSV_PATH.exists()
        df.to_csv(config.DATASET_CSV_PATH, mode="a", header=header, index=False)
        return True

    def record_gesture_session(
        self,
        label: str,
        duration_sec: float = 3.0,
        sample_hz: float = 50.0,
        hand_mode: str = "both",
        progress_cb: Optional[Callable[[float, int], None]] = None,
        done_cb: Optional[Callable[[int], None]] = None
    ):
        """
        Record a stream of frames for a specific ASL sign over a set duration.
        Supports 1-Hand ("right" or "left") or 2-Hands ("both").
        """
        if self.is_recording:
            logger.warning("Recording already in progress.")
            return

        def _worker():
            self.is_recording = True
            label_clean = label.strip().upper()
            interval = 1.0 / sample_hz
            total_samples = int(duration_sec * sample_hz)
            collected_rows = []

            mode_lower = str(hand_mode).lower().strip()
            if mode_lower in ["right", "one_hand_right", "1-hand (right)"]:
                cols = config.RIGHT_FEATURE_COLUMNS
                actual_mode = "RIGHT"
            elif mode_lower in ["left", "one_hand_left", "1-hand (left)"]:
                cols = config.LEFT_FEATURE_COLUMNS
                actual_mode = "LEFT"
            else:
                cols = config.DUAL_FEATURE_COLUMNS
                actual_mode = "DUAL"

            start_t = time.time()
            for idx in range(total_samples):
                if not self.is_recording:
                    break
                t_frame_start = time.time()
                vec = self.receiver.get_synchronized_feature_vector(hand_mode=hand_mode)
                row = {
                    "timestamp": time.time(),
                    "label": label_clean,
                    "hand_mode": actual_mode,
                    **{col: float(val) for col, val in zip(cols, vec)}
                }
                collected_rows.append(row)

                progress = (idx + 1) / total_samples
                if progress_cb:
                    progress_cb(progress, idx + 1)

                elapsed = time.time() - t_frame_start
                sleep_t = interval - elapsed
                if sleep_t > 0:
                    time.sleep(sleep_t)

            if collected_rows:
                df = pd.DataFrame(collected_rows)
                header = not config.DATASET_CSV_PATH.exists()
                df.to_csv(config.DATASET_CSV_PATH, mode="a", header=header, index=False)
                logger.info(f"Saved {len(collected_rows)} frames for gesture '{label_clean}' (Mode: {actual_mode})")

            self.is_recording = False
            if done_cb:
                done_cb(len(collected_rows))

        self.recording_thread = threading.Thread(target=_worker, daemon=True)
        self.recording_thread.start()

    def record_static_burst(
        self,
        label: str,
        count: int = 50,
        duration_sec: float = 2.5,
        hand_mode: str = "both",
        progress_cb: Optional[Callable[[float, int, int], None]] = None,
        done_cb: Optional[Callable[[int], None]] = None
    ):
        """
        Record 50+ discrete snapshots for a static ASL pose over a short duration.
        Allows the user to hold the handshape while shifting their hand across signing
        space to capture natural translational and positional variations.
        """
        if self.is_recording:
            logger.warning("Recording already in progress.")
            return

        def _worker():
            self.is_recording = True
            label_clean = label.strip().upper()
            total_samples = max(int(count), 10)
            dur = max(float(duration_sec), 0.5)
            interval = dur / float(total_samples)
            collected_rows = []

            mode_lower = str(hand_mode).lower().strip()
            if mode_lower in ["right", "one_hand_right", "1-hand (right)"]:
                cols = config.RIGHT_FEATURE_COLUMNS
                actual_mode = "RIGHT"
            elif mode_lower in ["left", "one_hand_left", "1-hand (left)"]:
                cols = config.LEFT_FEATURE_COLUMNS
                actual_mode = "LEFT"
            else:
                cols = config.DUAL_FEATURE_COLUMNS
                actual_mode = "DUAL"

            logger.info(f"Starting Static Pose Burst capture: {total_samples} snapshots for '{label_clean}' over {dur:.1f}s ({actual_mode} mode)")

            for idx in range(total_samples):
                if not self.is_recording:
                    break
                t_frame_start = time.time()
                vec = self.receiver.get_synchronized_feature_vector(hand_mode=hand_mode)
                row = {
                    "timestamp": time.time(),
                    "label": label_clean,
                    "hand_mode": actual_mode,
                    **{col: float(val) for col, val in zip(cols, vec)}
                }
                collected_rows.append(row)

                progress = (idx + 1) / float(total_samples)
                if progress_cb:
                    try:
                        progress_cb(progress, idx + 1, total_samples)
                    except TypeError:
                        progress_cb(progress, idx + 1)

                elapsed = time.time() - t_frame_start
                sleep_t = interval - elapsed
                if sleep_t > 0:
                    time.sleep(sleep_t)

            if collected_rows:
                df = pd.DataFrame(collected_rows)
                header = not config.DATASET_CSV_PATH.exists()
                df.to_csv(config.DATASET_CSV_PATH, mode="a", header=header, index=False)
                logger.info(f"Saved {len(collected_rows)} static burst snapshots for '{label_clean}' (Mode: {actual_mode})")

            self.is_recording = False
            if done_cb:
                done_cb(len(collected_rows))

        self.recording_thread = threading.Thread(target=_worker, daemon=True)
        self.recording_thread.start()

    def cancel_recording(self):
        """Interrupt active recording session."""
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=0.5)

    def get_dataset_summary(self) -> Dict[str, int]:
        """Return sample counts per gesture label."""
        if not config.DATASET_CSV_PATH.exists():
            return {}
        try:
            df = pd.read_csv(config.DATASET_CSV_PATH)
            if "label" not in df.columns:
                return {}
            return df["label"].value_counts().to_dict()
        except Exception as e:
            logger.error(f"Failed to read dataset: {e}")
            return {}

    def clear_dataset(self):
        """Wipe dataset file."""
        if config.DATASET_CSV_PATH.exists():
            config.DATASET_CSV_PATH.unlink()
            logger.info("Cleared dataset CSV.")

    def delete_gesture_samples(self, label: str) -> int:
        """Remove all entries belonging to a given label."""
        if not config.DATASET_CSV_PATH.exists():
            return 0
        df = pd.read_csv(config.DATASET_CSV_PATH)
        initial_len = len(df)
        df = df[df["label"] != label.strip().upper()]
        df.to_csv(config.DATASET_CSV_PATH, index=False)
        deleted = initial_len - len(df)
        logger.info(f"Deleted {deleted} samples of '{label}'")
        return deleted

    def get_dataset_info(self) -> Dict[str, Any]:
        """Return comprehensive metadata about the current dataset file."""
        if not config.DATASET_CSV_PATH.exists():
            return {"exists": False, "samples": 0, "classes": [], "mode": "None", "num_features": 0}
        try:
            df = pd.read_csv(config.DATASET_CSV_PATH)
            if df.empty or "label" not in df.columns:
                return {"exists": True, "samples": 0, "classes": [], "mode": "Empty", "num_features": 0}

            # Filter out metadata columns
            meta_cols = {"timestamp", "label", "hand_mode"}
            feature_cols = [col for col in df.columns if col not in meta_cols]

            has_right = any(col.upper().startswith("R_") for col in feature_cols)
            has_left = any(col.upper().startswith("L_") for col in feature_cols)

            if has_right and has_left:
                mode = "DUAL (28 Features)"
            elif has_right:
                mode = "RIGHT HAND (14 Features)"
            elif has_left:
                mode = "LEFT HAND (14 Features)"
            else:
                mode = f"Custom ({len(feature_cols)} Features)"

            classes = sorted(df["label"].dropna().unique().tolist())
            return {
                "exists": True,
                "samples": len(df),
                "classes": classes,
                "mode": mode,
                "num_features": len(feature_cols)
            }
        except Exception as e:
            logger.error(f"Failed to get dataset info: {e}")
            return {"exists": False, "samples": 0, "classes": [], "mode": "Error", "num_features": 0}

    def generate_synthetic_bootstrap_dataset(self, samples_per_class: int = 60, hand_mode: str = "right"):
        """
        Generate realistic synthetic data for common ASL signs to allow
        immediate testing of the ML and Translation pipeline before physical gloves are connected.
        Supports single hand (right/left) or dual hands.
        """
        logger.info(f"Generating synthetic bootstrap dataset for ASL signs (hand_mode: {hand_mode})...")
        # Define finger deflection signatures for select ASL signs:
        # [Thumb, Index, Middle, Ring, Pinky] (0.0 = straight, 1.0 = bent)
        hand_signatures = {
            "IDLE": ([0.05, 0.05, 0.05, 0.05, 0.05], [0.05, 0.05, 0.05, 0.05, 0.05]),
            "A": ([0.2, 0.9, 0.9, 0.9, 0.9], [0.2, 0.9, 0.9, 0.9, 0.9]),
            "B": ([0.9, 0.1, 0.1, 0.1, 0.1], [0.9, 0.1, 0.1, 0.1, 0.1]),
            "C": ([0.5, 0.5, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5, 0.5]),
            "D": ([0.8, 0.1, 0.8, 0.8, 0.8], [0.8, 0.1, 0.8, 0.8, 0.8]),
            "L": ([0.1, 0.1, 0.9, 0.9, 0.9], [0.1, 0.1, 0.9, 0.9, 0.9]),
            "Y": ([0.1, 0.9, 0.9, 0.9, 0.1], [0.1, 0.9, 0.9, 0.9, 0.1]),
            "HELLO": ([0.2, 0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1, 0.1]),
            "THANK_YOU": ([0.1, 0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1, 0.1]),
            "PLEASE": ([0.2, 0.1, 0.1, 0.1, 0.1], [0.8, 0.8, 0.8, 0.8, 0.8]),
            "YES": ([0.9, 0.9, 0.9, 0.9, 0.9], [0.8, 0.8, 0.8, 0.8, 0.8]),
            "NO": ([0.1, 0.7, 0.7, 0.9, 0.9], [0.8, 0.8, 0.8, 0.8, 0.8]),
            "HELP": ([0.1, 0.8, 0.8, 0.8, 0.8], [0.1, 0.1, 0.1, 0.1, 0.1]),
            "WATER": ([0.8, 0.1, 0.1, 0.1, 0.8], [0.8, 0.8, 0.8, 0.8, 0.8]),
            "FOOD": ([0.6, 0.6, 0.6, 0.6, 0.6], [0.8, 0.8, 0.8, 0.8, 0.8]),
            "I_LOVE_YOU": ([0.1, 0.1, 0.9, 0.9, 0.1], [0.1, 0.1, 0.9, 0.9, 0.1]),
            "GOOD_MORNING": ([0.2, 0.2, 0.2, 0.2, 0.2], [0.1, 0.1, 0.1, 0.1, 0.1]),
            "HOW_ARE_YOU": ([0.3, 0.2, 0.2, 0.3, 0.3], [0.3, 0.2, 0.2, 0.3, 0.3]),
            "DOCTOR": ([0.8, 0.2, 0.2, 0.8, 0.8], [0.1, 0.1, 0.1, 0.1, 0.1]),
            "FAMILY": ([0.7, 0.7, 0.1, 0.1, 0.1], [0.7, 0.7, 0.1, 0.1, 0.1]),
            "GOODBYE": ([0.2, 0.1, 0.1, 0.1, 0.1], [0.2, 0.1, 0.1, 0.1, 0.1])
        }

        mode_clean = str(hand_mode).lower().strip()
        if mode_clean in ["right", "one_hand_right", "1_hand_right", "1-hand"]:
            cols = config.RIGHT_FEATURE_COLUMNS
            actual_mode = "RIGHT"
        elif mode_clean in ["left", "one_hand_left", "1_hand_left"]:
            cols = config.LEFT_FEATURE_COLUMNS
            actual_mode = "LEFT"
        else:
            cols = config.DUAL_FEATURE_COLUMNS
            actual_mode = "DUAL"

        all_rows = []
        for gesture, (l_flex_base, r_flex_base) in hand_signatures.items():
            for _ in range(samples_per_class):
                # 1. Flex Sensors: finger flexion with muscle micro-deviations
                l_flex = np.clip(np.array(l_flex_base) + np.random.normal(0, 0.03, 5), 0, 1)
                r_flex = np.clip(np.array(r_flex_base) + np.random.normal(0, 0.03, 5), 0, 1)

                # 2. Accelerometer: Hand in 3D space with translation acceleration & tilt variations (±15°)
                l_tilt_pitch = np.random.uniform(-0.25, 0.25)
                l_tilt_roll = np.random.uniform(-0.25, 0.25)
                r_tilt_pitch = np.random.uniform(-0.25, 0.25)
                r_tilt_roll = np.random.uniform(-0.25, 0.25)

                l_accel_trans = np.random.normal(0, 0.12, 3) # Spatial translational motion
                r_accel_trans = np.random.normal(0, 0.12, 3)
                l_accel = np.array([l_tilt_roll, l_tilt_pitch, 0.98]) + l_accel_trans
                r_accel = np.array([r_tilt_roll, r_tilt_pitch, 0.98]) + r_accel_trans

                # 3. Gyroscope: Involuntary translation drift and tremors
                l_gyro = np.random.normal(0, 0.12, 3)
                r_gyro = np.random.normal(0, 0.12, 3)

                # 4. Magnetometer: Multi-directional room ambient magnetic field shifts
                mag_room_offset = np.random.normal(0, 0.25, 3)
                l_mag = np.array([0.5, -0.3, 0.8]) + mag_room_offset + np.random.normal(0, 0.1, 3)
                r_mag = np.array([-0.4, 0.6, 0.7]) + mag_room_offset + np.random.normal(0, 0.1, 3)

                if actual_mode == "RIGHT":
                    vec = np.concatenate([r_flex, r_accel, r_gyro, r_mag])
                elif actual_mode == "LEFT":
                    vec = np.concatenate([l_flex, l_accel, l_gyro, l_mag])
                else:
                    vec = np.concatenate([
                        l_flex, l_accel, l_gyro, l_mag,
                        r_flex, r_accel, r_gyro, r_mag
                    ])

                row = {
                    "timestamp": time.time(),
                    "label": gesture,
                    "hand_mode": actual_mode,
                    **{col: float(val) for col, val in zip(cols, vec)}
                }
                all_rows.append(row)

        df = pd.DataFrame(all_rows)
        df.to_csv(config.DATASET_CSV_PATH, index=False)
        logger.info(f"Generated {len(all_rows)} synthetic samples for {actual_mode} mode across {len(hand_signatures)} classes.")

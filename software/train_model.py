"""
Model Training Module
Trains and validates machine learning classifiers (Random Forest / MLP) on dual-glove ASL features.
Saves model weights, feature scalers, and label encoders for real-time inference.
"""
import logging
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ModelTrainer")

import json
import time

def augment_spatial_data(
    X: np.ndarray,
    y: np.ndarray,
    feature_cols: list,
    factor: int = 3,
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Augment training samples with simulated 3D spatial translations, motion jitter, and positional shifts.
    Guarantees that the trained model is invariant to where the hand is located in space or moving
    between positions over time.
    
    Augmentations:
    - Accelerometer: Translational linear acceleration (±0.12g) + tilt jitter (±15°).
    - Gyroscope: Involuntary translation drift & tremors (±0.15).
    - Magnetometer: Multi-directional room magnetic gradient perturbations.
    - Flex Sensors: Biometric muscle micro-variations (±0.03).
    """
    rng = np.random.default_rng(random_state)
    
    flex_indices = [i for i, c in enumerate(feature_cols) if "flex" in c.lower()]
    accel_indices = [i for i, c in enumerate(feature_cols) if "accel" in c.lower()]
    gyro_indices = [i for i, c in enumerate(feature_cols) if "gyro" in c.lower()]
    mag_indices = [i for i, c in enumerate(feature_cols) if "mag" in c.lower()]
    
    X_aug_list = [X]
    y_aug_list = [y]
    
    for _ in range(factor):
        X_new = X.copy()
        
        # 1. Flex Sensors: subtle flexion relaxation/muscle jitter
        if flex_indices:
            noise_flex = rng.normal(0, 0.03, size=(len(X), len(flex_indices)))
            X_new[:, flex_indices] = np.clip(X_new[:, flex_indices] + noise_flex, 0.0, 1.0)
            
        # 2. Accelerometer: Hand spatial translation acceleration (±0.12g) + 3D tilt jitter (±15°)
        if accel_indices:
            noise_accel = rng.normal(0, 0.12, size=(len(X), len(accel_indices)))
            tilt_angles = rng.uniform(-np.radians(15), np.radians(15), size=(len(X), len(accel_indices)))
            X_new[:, accel_indices] = (X_new[:, accel_indices] * np.cos(tilt_angles)) + noise_accel
            
        # 3. Gyroscope: Involuntary translation drift & motion tremors
        if gyro_indices:
            noise_gyro = rng.normal(0, 0.15, size=(len(X), len(gyro_indices)))
            X_new[:, gyro_indices] = X_new[:, gyro_indices] + noise_gyro
            
        # 4. Magnetometer: Room environmental field shifts & local interference
        if mag_indices:
            mag_scale = rng.normal(1.0, 0.15, size=(len(X), len(mag_indices)))
            mag_shift = rng.normal(0.0, 0.20, size=(len(X), len(mag_indices)))
            X_new[:, mag_indices] = (X_new[:, mag_indices] * mag_scale) + mag_shift
            
        X_aug_list.append(X_new)
        y_aug_list.append(y.copy())
        
    return np.vstack(X_aug_list), np.concatenate(y_aug_list)

def train_classifier(
    model_type: str = "rf",
    hand_mode: str = "auto",
    test_size: float = 0.2,
    random_state: int = 42,
    spatial_augmentation: bool = True,
    augmentation_factor: int = 3
) -> Tuple[bool, Dict[str, Any]]:
    """
    Train ASL classifier using data in config.DATASET_CSV_PATH.
    
    Args:
        model_type: 'rf' for Random Forest, 'mlp' for Multi-Layer Perceptron.
        hand_mode: 'auto', 'right' (1 Hand), 'left' (1 Hand), or 'dual' (2 Hands).
        test_size: Fraction of samples reserved for testing (0.1 - 0.3).
        random_state: Random seed for reproducibility.
        spatial_augmentation: If True, augment training data with spatial translations and tilts.
        augmentation_factor: Number of synthetic augmented copies per training sample.
        
    Returns:
        (success_bool, metrics_dict)
    """
    if not config.DATASET_CSV_PATH.exists():
        msg = f"Dataset file does not exist at {config.DATASET_CSV_PATH}"
        logger.error(msg)
        return False, {"error": msg}

    try:
        df = pd.read_csv(config.DATASET_CSV_PATH)
        if len(df) < 10:
            msg = f"Dataset too small ({len(df)} samples). Record more samples before training."
            logger.error(msg)
            return False, {"error": msg}

        # Resolve hand mode and feature columns
        mode_clean = str(hand_mode).lower().strip()
        has_right_cols = all(c in df.columns for c in config.RIGHT_FEATURE_COLUMNS)
        has_left_cols = all(c in df.columns for c in config.LEFT_FEATURE_COLUMNS)

        if mode_clean in ["right", "one_hand_right", "1_hand_right", "1-hand (right)"]:
            if not has_right_cols:
                return False, {"error": "Dataset does not contain Right Hand feature columns."}
            selected_cols = list(config.RIGHT_FEATURE_COLUMNS)
            resolved_mode = "right"
        elif mode_clean in ["left", "one_hand_left", "1_hand_left", "1-hand (left)"]:
            if not has_left_cols:
                return False, {"error": "Dataset does not contain Left Hand feature columns."}
            selected_cols = list(config.LEFT_FEATURE_COLUMNS)
            resolved_mode = "left"
        elif mode_clean in ["dual", "both", "2_hands", "dual glove"]:
            if not (has_right_cols and has_left_cols):
                return False, {"error": "Dual glove mode requires both Left and Right hand feature columns in dataset."}
            selected_cols = list(config.DUAL_FEATURE_COLUMNS)
            resolved_mode = "dual"
        else: # "auto"
            if has_right_cols and has_left_cols:
                # Check if one hand is completely static/disconnected (std close to 0)
                l_var = df[config.LEFT_FEATURE_COLUMNS].std().sum()
                r_var = df[config.RIGHT_FEATURE_COLUMNS].std().sum()
                if l_var < 0.05 and r_var >= 0.05:
                    selected_cols = list(config.RIGHT_FEATURE_COLUMNS)
                    resolved_mode = "right"
                elif r_var < 0.05 and l_var >= 0.05:
                    selected_cols = list(config.LEFT_FEATURE_COLUMNS)
                    resolved_mode = "left"
                else:
                    selected_cols = list(config.DUAL_FEATURE_COLUMNS)
                    resolved_mode = "dual"
            elif has_right_cols:
                selected_cols = list(config.RIGHT_FEATURE_COLUMNS)
                resolved_mode = "right"
            elif has_left_cols:
                selected_cols = list(config.LEFT_FEATURE_COLUMNS)
                resolved_mode = "left"
            else:
                return False, {"error": "Dataset does not have required sensory columns."}

        X = df[selected_cols].values.astype(np.float32)
        y_raw = df["label"].values.astype(str)

        # Encode categorical gesture labels
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(y_raw)
        classes = list(label_encoder.classes_)

        if len(classes) < 2:
            msg = "Need at least 2 distinct gesture classes to train a classifier."
            logger.error(msg)
            return False, {"error": msg}

        # Check if stratification is safe
        counts = np.bincount(y)
        can_stratify = len(counts) > 0 and np.min(counts) >= 2
        stratify_opt = y if can_stratify else None

        # Train/Test Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify_opt
        )

        orig_train_samples = len(X_train)

        # Apply Spatial Translation Invariance Augmentation to training set
        if spatial_augmentation and len(X_train) > 0:
            logger.info(f"Applying spatial translation invariance augmentation (factor={augmentation_factor})...")
            X_train, y_train = augment_spatial_data(
                X_train, y_train, selected_cols, factor=augmentation_factor, random_state=random_state
            )
            logger.info(f"Training dataset augmented from {orig_train_samples} to {len(X_train)} samples across space.")

        # Standardize features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Initialize model
        if model_type.lower() == "mlp":
            model = MLPClassifier(
                hidden_layer_sizes=(128, 64),
                activation="relu",
                max_iter=300,
                random_state=random_state,
                early_stopping=True
            )
        else: # Default: Random Forest
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=16,
                n_jobs=-1,
                random_state=random_state
            )

        logger.info(f"Training {model.__class__.__name__} ({resolved_mode.upper()} mode, {len(selected_cols)} features) on {len(X_train)} samples across {len(classes)} classes...")
        model.fit(X_train_scaled, y_train)

        # Evaluate performance
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, target_names=classes, output_dict=True, zero_division=0)
        cm = confusion_matrix(y_test, y_pred).tolist()

        logger.info(f"Training completed successfully! Test Accuracy: {accuracy * 100:.2f}% (Mode: {resolved_mode.upper()})")

        # Save artifacts
        joblib.dump(model, config.MODEL_PATH)
        joblib.dump(scaler, config.SCALER_PATH)
        joblib.dump(label_encoder, config.LABEL_ENCODER_PATH)

        # Save model metadata so recognizer and UI adapt dynamically
        metadata = {
            "hand_mode": resolved_mode,
            "feature_columns": selected_cols,
            "num_features": len(selected_cols),
            "classes": classes,
            "accuracy": float(accuracy),
            "model_type": model_type.lower(),
            "train_samples": len(X_train),
            "original_train_samples": orig_train_samples,
            "spatial_augmentation": bool(spatial_augmentation),
            "test_samples": len(X_test),
            "timestamp": time.time()
        }
        with open(config.MODEL_METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)

        metrics = {
            "accuracy": float(accuracy),
            "num_classes": len(classes),
            "classes": classes,
            "train_samples": len(X_train),
            "original_train_samples": orig_train_samples,
            "spatial_augmentation": bool(spatial_augmentation),
            "test_samples": len(X_test),
            "hand_mode": resolved_mode,
            "num_features": len(selected_cols),
            "feature_columns": selected_cols,
            "report": report,
            "confusion_matrix": cm,
            "model_type": model_type
        }
        return True, metrics

    except Exception as e:
        logger.exception("Error during model training:")
        return False, {"error": str(e)}

if __name__ == "__main__":
    from dataset_recorder import DatasetRecorder
    from receiver import DualGloveReceiver
    # If no data exists, generate bootstrap dataset
    if not config.DATASET_CSV_PATH.exists():
        rec = DatasetRecorder(DualGloveReceiver())
        rec.generate_synthetic_bootstrap_dataset()
    success, metrics = train_classifier()
    print("Result:", "Success" if success else "Failed")
    if success:
        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print("Classes:", metrics['classes'])

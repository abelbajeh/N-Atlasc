# End-to-End Workflow & Pipeline Architecture
## ASL to Nigerian Languages Translation System

This document outlines the complete dataflow and processing pipeline from raw sensory capture on two hands to neural translation and spoken multilingual speech output.

---

### 1. High-Level Pipeline Architecture

```text
  [LEFT GLOVE]                          [RIGHT GLOVE]
  (5 Flex + MPU-9250)                   (5 Flex + MPU-9250)
         │                                     │
    ESP32 ADC + I2C                       ESP32 ADC + I2C
  (50Hz Sampling Rate)                  (50Hz Sampling Rate)
         │                                     │
         └─────────────┬───────────────────────┘
                       │
             UDP Packet Broadcast
          (Wi-Fi 802.11b/g/n / BLE)
                       │
                       ▼
         ┌───────────────────────────┐
         │   Python Host Receiver    │  (receiver.py)
         │  - Packet De-jittering    │
         │  - Left/Right Time-Sync   │
         │  - Calibration Scaling    │
         └─────────────┬─────────────┘
                       │ Synchronized 28-D Feature Vector
                       ▼
         ┌───────────────────────────┐
         │   Feature Normalization   │  (dataset_recorder.py)
         │  - Finger Curvatures: 0-1 │
         │  - 3D Accel & Gyro Rates  │
         │  - Sliding Window (200ms) │
         └─────────────┬─────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │ Gesture Recognizer Engine │  (gesture_recognizer.py)
         │  - Random Forest / MLP    │
         │  - Confidence Gating      │
         │  - Debounce & Hold Logic  │
         └─────────────┬─────────────┘
                       │ ASL Signs / Gloss Sequence ("HELLO", "HOW", "YOU")
                       ▼
         ┌───────────────────────────┐
         │  Sentence Builder Engine  │  (sentence_builder.py)
         │  - Gloss to English       │
         │  - Grammar Restructuring  │  --> "Hello, how are you?"
         └─────────────┬─────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │   N-Atlas Translator      │  (translator.py)
         │  - Multilingual Seq2Seq   │
         │  - English -> Yoruba      │  --> "Ẹ n lẹ o, bawo ni o ṣe wa?"
         │  - English -> Igbo        │  --> "Ndewo, kedu ka ị mere?"
         │  - English -> Hausa       │  --> "Sannu, yaya kake?"
         └─────────────┬─────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │     TTS Audio Engine      │  (tts_engine.py)
         │  - Native Voice Playback  │
         │  - Spoken Audio Output    │
         └───────────────────────────┘
```

---

### 2. Sensor Feature Vector Specifications

At each time-step $t$, data packets from both the Left Hand and Right Hand are paired by closest timestamp:

| Feature Index | Hand | Feature | Description | Range |
| :--- | :--- | :--- | :--- | :--- |
| `0 - 4` | Left Hand | Flex 1 - 5 | Thumb, Index, Middle, Ring, Pinky | Normalized `[0.0, 1.0]` |
| `5 - 7` | Left Hand | Accel X, Y, Z | Linear acceleration (m/s² or g) | `[-2.0g, +2.0g]` |
| `8 - 10` | Left Hand | Gyro X, Y, Z | Angular velocity (deg/s) | `[-500, +500]` |
| `11 - 13` | Left Hand | Mag X, Y, Z | Magnetic orientation (µT) | `[-4800, +4800]` |
| `14 - 18` | Right Hand| Flex 1 - 5 | Thumb, Index, Middle, Ring, Pinky | Normalized `[0.0, 1.0]` |
| `19 - 21` | Right Hand| Accel X, Y, Z | Linear acceleration (m/s² or g) | `[-2.0g, +2.0g]` |
| `22 - 24` | Right Hand| Gyro X, Y, Z | Angular velocity (deg/s) | `[-500, +500]` |
| `25 - 27` | Right Hand| Mag X, Y, Z | Magnetic orientation (µT) | `[-4800, +4800]` |

Total instantaneous feature vector size: **28 continuous float features**.

For dynamic gestures (e.g., gestures with movement like "HELLO", "THANK YOU", "PLEASE"):
A sliding window of $N = 10$ frames ($200\text{ ms}$ at 50Hz) is flattened or processed using statistical aggregations (mean, std, min, max, delta), producing a robust invariant feature representation.

---

### 3. Machine Learning Classification

The repository supports two complementary ML strategies:
1. **Ensemble Classifier (Random Forest / Gradient Boosting):**
   - Ideal for static ASL handshapes and letters (A–Z) and two-handed static signs.
   - Extremely fast (<2ms inference on CPU).
   - High interpretability via feature importance.
2. **Deep Neural Network (MLP / 1D-CNN):**
   - For continuous stream classification and temporal trajectory tracking.
   - Outputs class probabilities with softmax thresholding (e.g., accept only if confidence > 0.85).

---

### 4. Sentence Formation & Grammar Reconstruction

Raw ASL often uses **Topic-Comment** structure rather than English **Subject-Verb-Object (SVO)** structure (e.g., ASL: *"STORE ME GO"* $\rightarrow$ English: *"I am going to the store"*).

The sentence builder implements:
- **Sign Debouncing:** Requires a sign to be held stably for $\ge 300\text{ ms}$ before registering to prevent transition noise.
- **Gloss Accumulation:** Appends distinct recognized signs into a gloss buffer.
- **Grammar Restructuring:** Converts gloss sequences into natural English sentences using grammatical lookup rules and optional language model smoothing.

---

### 5. Translation to Nigerian Languages via N-Atlas

The English sentence is fed into the **N-Atlas** model:
- **Languages Supported:**
  - **Yoruba (`yor`):** Southwestern Nigeria, Benin, Togo.
  - **Igbo (`ibo`):** Southeastern Nigeria.
  - **Hausa (`hau`):** Northern Nigeria, Niger, West Africa.
- The pipeline supports direct Hugging Face transformer inference, quantization for low-latency CPU/laptop execution, and fallback rule-based mapping when running in offline low-resource environments.

---

### 6. Multilingual Text-To-Speech (TTS)

Once translation completes, the synthesized text is passed to the TTS module:
- English, Yoruba, Igbo, and Hausa speech synthesis.
- Supports `gTTS` (Google Neural TTS for African accents), `edge-tts` (Microsoft Neural multi-accent), and offline fallback `pyttsx3`.
- Plays audio through the host speakers and displays synchronized subtitles on the UI.

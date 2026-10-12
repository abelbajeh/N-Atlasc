# N-Atlas: Dual-Glove ASL Translator to Nigerian Languages
### Real-Time American Sign Language (ASL) Recognition & Neural Translation to Yorùbá, Igbo, and Hausa with Text-To-Speech

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Hardware-ESP32](https://img.shields.io/badge/Hardware-ESP32%20Dual%20Gloves-brightgreen.svg)](https://www.espressif.com/)
[![IMU-MPU9250](https://img.shields.io/badge/Sensors-MPU9250%20+%2010x%20Flex-orange.svg)](#)
[![NLP-N--Atlas](https://img.shields.io/badge/Translation-N--Atlas%20Multilingual-purple.svg)](#)
[![TTS-Multilingual](https://img.shields.io/badge/Speech-TTS%20Yoruba%20|%20Igbo%20|%20Hausa-teal.svg)](#)

---

## 📌 Project Overview

This system bridges communication between the Deaf/Hard-of-Hearing community and speakers of indigenous Nigerian languages. Using **two smart sensor gloves** (Left and Right hand), the system captures finger flexions and 3D spatial wrist kinematics at 50 Hz, transmits telemetry over Wi-Fi UDP (or Bluetooth) to a host PC application, recognizes ASL gestures/signs, constructs fluent English sentences, and translates them into **Yorùbá**, **Igbo**, or **Hausa** using the **N-Atlas** multilingual model with synchronized **Text-to-Speech (TTS)** voice output.

```text
 ┌──────────────┐     ┌──────────────┐
 │  LEFT GLOVE  │     │ RIGHT GLOVE  │
 │ 5x Bend Sens │     │ 5x Bend Sens │
 │ 1x MPU-9250  │     │ 1x MPU-9250  │
 └──────┬───────┘     └──────┬───────┘
        │   Wi-Fi UDP (50Hz) │
        └───────────┬────────┘
                    ▼
       ┌────────────────────────┐
       │   Python Desktop GUI   │
       │  (receiver.py @ 5005)  │
       └────────────┬───────────┘
                    ▼
       ┌────────────────────────┐
       │   Gesture Classifier   │  --> Recognizes ASL Handshapes / Signs
       │ (Random Forest / MLP)  │
       └────────────┬───────────┘
                    ▼
       ┌────────────────────────┐
       │    Sentence Builder    │  --> Assembles Glosses & Letters into English
       └────────────┬───────────┘
                    ▼
       ┌────────────────────────┐
       │  N-Atlas Multilingual  │  --> Translates to Yorùbá, Igbo, or Hausa
       │   Translation Model    │
       └────────────┬───────────┘
                    ▼
       ┌────────────────────────┐
       │   Multilingual TTS     │  --> Speaks aloud in English or Nigerian Voice
       └────────────────────────┘
```

---

## 📁 Repository Structure

```
N-Atlas/
├── docs/
│   ├── BOM_MATERIALS.md              # Complete Bill of Materials, component specs & sizing
│   ├── CIRCUIT_DIAGRAM.md            # Circuit schematics, pin tables & voltage dividers
│   ├── HARDWARE_SETUP_GUIDE.md       # Step-by-step glove fabrication, wiring & mounting
│   ├── WORKFLOW_AND_PIPELINE.md      # Data pipeline, 28-D feature vector & ML architecture
│   └── N_ATLAS_TRANSLATION_GUIDE.md  # N-Atlas model loading, language tags & tokenization
├── firmware/
│   ├── common/
│   │   └── GlovePacket.h             # Shared binary struct & telemetry protocol
│   ├── esp32_glove_left/
│   │   ├── config.h                  # Left glove pinouts, SSID, and UDP destination
│   │   └── esp32_glove_left.ino      # ESP32 firmware for Left Hand
│   └── esp32_glove_right/
│       ├── config.h                  # Right glove pinouts, SSID, and UDP destination
│       └── esp32_glove_right.ino     # ESP32 firmware for Right Hand
├── software/
│   ├── app.py                        # Full-featured Modern Desktop GUI Application
│   ├── config.py                     # Global paths, network ports, and language settings
│   ├── receiver.py                   # Wi-Fi UDP & Bluetooth receiver + simulator
│   ├── dataset_recorder.py           # Dataset collection studio & synthetic bootstrapper
│   ├── train_model.py                # Classifier training (Random Forest / MLP)
│   ├── gesture_recognizer.py         # Real-time inference, confidence gating & debouncing
│   ├── sentence_builder.py           # ASL glosses & fingerspelling to English grammar engine
│   ├── translator.py                 # N-Atlas multilingual translator (Yoruba, Igbo, Hausa)
│   ├── tts_engine.py                 # Multilingual Text-to-Speech audio synthesizer
│   └── requirements.txt              # Python library dependencies
├── data/
│   ├── gestures/                     # Saved CSV datasets of recorded ASL poses
│   ├── models/                       # Trained classifier weights & label encoders
│   └── calibration/                  # Glove min/max ADC calibration profiles
└── README.md                         # Master documentation (this file)
```

---

## ⚡ Hardware Pinout & Wiring Summary

> **CRITICAL ESP32 DESIGN RULE:**  
> When ESP32 Wi-Fi is active, **ADC2 is hardware-disabled**. All flex sensors **MUST** be wired to **ADC1** pins (`GPIO 32, 34, 35, 36, 39`).

### Left & Right Hand ESP32 Pin Connections

| Component | Pin | ESP32 GPIO | Description |
| :--- | :--- | :--- | :--- |
| **Thumb Flex** | Divider Node | `GPIO 36 (VP)` | ADC1_CH0 (Analog 12-bit) |
| **Index Flex** | Divider Node | `GPIO 39 (VN)` | ADC1_CH3 (Analog 12-bit) |
| **Middle Flex** | Divider Node | `GPIO 34` | ADC1_CH6 (Analog 12-bit) |
| **Ring Flex** | Divider Node | `GPIO 35` | ADC1_CH7 (Analog 12-bit) |
| **Pinky Flex** | Divider Node | `GPIO 32` | ADC1_CH4 (Analog 12-bit) |
| **MPU-9250** | SDA | `GPIO 21` | I2C Data |
| **MPU-9250** | SCL | `GPIO 22` | I2C Clock |
| **MPU-9250** | AD0 | `GND` | Sets I2C Address `0x68` |
| **MPU-9250 / Sensors** | VCC | `3.3V` | Regulated 3.3V Power Rail |
| **All Grounds** | GND | `GND` | Common Ground |

See [docs/CIRCUIT_DIAGRAM.md](file:///c:/Users/emmak/Desktop/SERIOUS%20PROJECTS/N-Atlas/docs/CIRCUIT_DIAGRAM.md) and [docs/BOM_MATERIALS.md](file:///c:/Users/emmak/Desktop/SERIOUS%20PROJECTS/N-Atlas/docs/BOM_MATERIALS.md) for full schematics and resistor calculations.

---

## 🚀 Quickstart Guide

### 1. Flash the ESP32 Glove Firmware

1. Install [Arduino IDE](https://www.arduino.cc/) or PlatformIO with the **ESP32 Board Package**.
2. Open `firmware/esp32_glove_right/esp32_glove_right.ino` (or `esp32_glove_left.ino`):
   - Edit `config.h` to set your local Wi-Fi SSID/password (e.g., `"KINGDOM"`).
   - **Zero Configuration:** You do NOT need to configure your PC's IP address! The ESP32 waits in Standby.
   - Connect the ESP32 via USB and click **Upload**.
   - Open Serial Monitor (115200 baud) — note the IP printed: `GLOVE IP: 192.168.205.82 | STATUS: STANDBY`.
3. Open the Python GUI (`python app.py`):
   - Enter the Glove IP into the Right IP (or Left IP) box.
   - Click **`🔗 Connect`**! Python will establish the link and activate telemetry immediately.

### 2. Install Python Dependencies

```powershell
cd "c:\Users\emmak\Desktop\SERIOUS PROJECTS\N-Atlas\software"
pip install -r requirements.txt
```

### 3. Launch the Desktop Application

```powershell
python app.py
```

---

## 🖥 Application Features & User Guide

### 1. Hardware Link & Inbuilt LED IP Tester (Header Bar)
* **IP Address Inputs:** Dedicated entry fields for **Left Hand IP** (default `192.168.4.2`) and **Right Hand IP** (default `192.168.4.3`) with automatic IP detection as soon as gloves connect.
* **Inbuilt Status LEDs:** Real-time visual mirrors of each glove's ESP32 GPIO 2 onboard LED:
  - `● INBUILT LED: OFF` (Gray): Glove is disconnected or searching for network.
  - `● INBUILT LED: ON (SOLID)` (Glowing Cyan / Green): Glove is connected to Wi-Fi and actively transmitting packets.
* **`[ ⚡ Ping ]` Button:** Transmits an active network ping probe to verify reachability and measure round-trip latency.
* **`[ 💡 Flash LED ]` Button:** Sends a command over UDP to physically flash the glove's onboard blue LED 5 times to physically identify which glove is Left or Right.

### 2. Live Telemetry & Calibration Tab

* **Dual-Hand Telemetry Bars:** Displays individual deflection percentages for all 10 fingers and 9-DOF IMU orientations (Ax, Ay, Az, Gx, Gy, Gz) in real-time.
* **One-Click Calibration:**
  1. Hold both hands flat on a table and click **"Set Flat Hand (0° Bend)"**.
  2. Make a tight fist with both hands and click **"Set Closed Fist (90° Bend)"**.
  3. Calibration values are automatically saved to `data/calibration/glove_calibration.json`.

### 2. Dataset Studio Tab
* Select or enter any ASL sign (e.g. `A`-`Z`, `HELLO`, `WATER`, `FOOD`, `HELP`, `THANK_YOU`, `DOCTOR`).
* Click **"⏺ Record Sign Stream"** to record 3 seconds (150 frames) of gesture telemetry.
* Or click **"⚡ Generate Bootstrap Data"** to instantly generate clean synthetic training data for quick testing!

### 3. Model Training & Evaluation Tab
* Choose between **Random Forest** (fast, robust) or **MLP Neural Network**.
* Click **"🚀 Train ASL Recognition Model"**.
* View real-time accuracy (typically >98%), confusion matrices, and class distributions.
* Automatically reloads the model into memory upon completion!

### 4. Live Translation & TTS Tab (Core Experience)
* **Real-Time Detector:** Shows currently recognized sign with confidence percentage and stability gating.
* **Sentence Builder:** Accumulates signs and fingerspelled letters into natural English phrases.
* **N-Atlas Translation:**
  - Select target language: **Yorùbá**, **Igbo**, or **Hausa**.
  - Displays accurate diacritics (ẹ, ọ, ṣ, à, á, ị, ụ, ṅ) and phonetic pronunciation guidelines!
* **Text-to-Speech:** Click **"🔊 Speak Translated Version (TTS)"** or **"🔊 Speak English"** for clear vocal playback.
* **Auto-Speak:** Toggle to automatically vocalize translated sentences as they are signed!

---

## 🌐 Supported Nigerian Languages & N-Atlas Model

| Language | Tone Diacritics Supported | Example English | Example Translation |
| :--- | :--- | :--- | :--- |
| **Yorùbá** | `Ẹ`, `Ọ`, `Ṣ`, `à`, `á`, `è`, `é` | "Please give me some water." | *"Ẹ jọ̀wọ́, ẹ fún mi ní omi."* |
| **Igbo** | `Ị`, `Ọ`, `Ụ`, `ṅ`, `ọ̀`, `ọ́` | "Please give me some water." | *"Biko nye m mmiri."* |
| **Hausa** | Standard Latin + Sahelean Orthography | "Please give me some water." | *"Don Allah bani ruwa."* |

For more details on neural transformer inference and tokenization, see [docs/N_ATLAS_TRANSLATION_GUIDE.md](file:///c:/Users/emmak/Desktop/SERIOUS%20PROJECTS/N-Atlas/docs/N_ATLAS_TRANSLATION_GUIDE.md).

---

## 🛠 Troubleshooting & FAQ

* **Wi-Fi connection drops or ESP32 won't connect:**  
  Make sure your laptop hotspot is 2.4 GHz (ESP32 does not support 5 GHz Wi-Fi).
* **Flex sensor readings fluctuate:**  
  Ensure $0.1\,\mu\text{F}$ filter capacitors are soldered between ADC pins and GND.
* **Testing without physical gloves:**  
  Simply check the **"Simulation Mode"** checkbox in the top header of the GUI to test the entire data pipeline, training, translation, and TTS system with synthetic gesture waveforms!

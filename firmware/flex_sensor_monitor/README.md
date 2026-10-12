# ESP32 Flex Sensor Monitor & Calibration Tool

This utility firmware allows you to monitor, debug, and calibrate all 5 flex bend sensors connected to your ESP32 before streaming telemetry to the N-Atlas Python translation GUI.

---

## 📌 Hardware Pinout (ADC1)

All flex sensors are wired to **ADC1** pins to maintain complete compatibility with the ESP32's Wi-Fi radio:

| Finger | ESP32 GPIO | ADC Channel | Divider Circuit | Expected Flat | Expected Bent |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Thumb** | `GPIO 36` (VP) | ADC1_CH0 | 3.3V ➔ Flex ➔ GPIO ➔ 22kΩ ➔ GND | ~2700 - 3000 | ~1000 - 1400 |
| **Index** | `GPIO 39` (VN) | ADC1_CH3 | 3.3V ➔ Flex ➔ GPIO ➔ 22kΩ ➔ GND | ~2700 - 3000 | ~1000 - 1400 |
| **Middle** | `GPIO 34` | ADC1_CH6 | 3.3V ➔ Flex ➔ GPIO ➔ 22kΩ ➔ GND | ~2700 - 3000 | ~1000 - 1400 |
| **Ring** | `GPIO 35` | ADC1_CH7 | 3.3V ➔ Flex ➔ GPIO ➔ 22kΩ ➔ GND | ~2700 - 3000 | ~1000 - 1400 |
| **Pinky** | `GPIO 32` | ADC1_CH4 | 3.3V ➔ Flex ➔ GPIO ➔ 22kΩ ➔ GND | ~2700 - 3000 | ~1000 - 1400 |

* **LED Indicator**: GPIO 2 (Blinks as heartbeat to confirm code execution)
* **Serial Baud Rate**: `115200` baud

---

## 🚀 How to Flash & Run

1. Open **Arduino IDE** (or VS Code with PlatformIO).
2. Open [`flex_sensor_monitor.ino`](file:///c:/Users/emmak/Desktop/SERIOUS%20PROJECTS/N-Atlas/firmware/flex_sensor_monitor/flex_sensor_monitor.ino).
3. Select your board:
   - **Board**: `ESP32 Dev Module`
   - **Upload Speed**: `921600` (or `115200`)
   - **Flash Frequency**: `80MHz`
   - **Port**: Select your ESP32 COM port (e.g., `COM3`, `COM4`)
4. Click **Upload** (Hold `BOOT` button on ESP32 if upload gets stuck at `Connecting...`).
5. Open **Tools ➔ Serial Monitor** and set baud rate to **115200**.

---

## ⌨️ Interactive Commands

Send any of the following characters in the Serial Monitor text box:

| Key | Mode / Action | Description |
| :---: | :--- | :--- |
| **`m`** or **`t`** | **Table Dashboard** | Real-time formatted table with Pin, Raw ADC, Volts, Min/Max, and Gauge bar. |
| **`p`** | **Serial Plotter** | Formats data for Arduino IDE Serial Plotter (`Ctrl + Shift + L`) for live waveform graphs. |
| **`j`** | **JSON Stream** | Prints clean JSON packets matching N-Atlas format. |
| **`c`** | **Print Calibration** | Outputs a JSON block ready to paste into `data/calibration/glove_calibration.json`. |
| **`r`** | **Reset Counters** | Resets all Min/Max recorded values to begin a new calibration run. |
| **`h`** | **Help Menu** | Prints command list. |

---

## 🎯 Step-by-Step Calibration Routine

1. Put the glove on your hand.
2. Open Serial Monitor (`115200` baud) and send `r` to reset counters.
3. **Extend your hand completely flat** on a table for 3 seconds.
4. **Make a tight fist**, curling all 5 fingers fully, for 3 seconds.
5. Move each finger individually through its full range of motion.
6. Send `c` in the Serial Monitor.
7. Copy the printed JSON block and update [`data/calibration/glove_calibration.json`](file:///c:/Users/emmak/Desktop/SERIOUS%20PROJECTS/N-Atlas/data/calibration/glove_calibration.json).

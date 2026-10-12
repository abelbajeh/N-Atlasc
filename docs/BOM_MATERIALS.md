# Bill of Materials (BOM) & Component Specifications
## ASL to Nigerian Languages Glove Translation System

This document outlines all hardware components, tools, specifications, and wiring considerations required to construct the dual-glove ASL recognition and translation system.

---

### 1. Primary Electronics (Per Set: Left & Right Hands)

| Item # | Component Description | Quantity | Specifications / Recommended Model | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **ESP32 Microcontroller Dev Board** | 2 | ESP32-WROOM-32 (30 or 38 pin), Dual-Core, 2.4 GHz Wi-Fi + BLE 4.2 | 1 per glove. Reads sensor ADCs, communicates with IMU over I2C, streams data wirelessly. |
| **2** | **Flex / Bend Sensors** | 10 | 2.2" or 4.5" Flex Sensors (Spectra Symbol or generic conductive polymer) | 5 per glove (Thumb, Index, Middle, Ring, Pinky). Resistance: ~10kΩ-25kΩ flat, ~60kΩ-100kΩ bent 90°. |
| **3** | **MPU-9250 9-DOF IMU Modules** | 2 | 9-Axis Gyroscope + Accelerometer + Magnetometer (AK8963), I2C interface | 1 per glove mounted on the back of the palm/wrist to measure 3D hand orientation, tilt, and motion. |
| **4** | **Fixed Resistors (Voltage Dividers)**| 10 | 22 kΩ (or 10 kΩ / 47 kΩ depending on flex sensor nominal resistance), 1/4W 1% Metal Film | Voltage divider reference resistors for ADC analog read. |
| **5** | **LiPo Batteries (3.7V)** | 2 | 3.7V 800mAh - 1200mAh Lithium Polymer Battery with JST connector | Portable, cordless glove power supply. |
| **6** | **LiPo Charging & Protection Board** | 2 | TP4056 Micro-USB / Type-C 5V 1A LiPo Charger Module with battery protection (DW01A) | Safe charging and low-voltage cutoff. |
| **7** | **Power Switch** | 2 | Miniature SPDT Slide Switch | Power on/off switch on glove wristband. |
| **8** | **Prototyping Board / Perfboard** | 2 | 4x6 cm double-sided PCB perfboard | Glove wrist breakout board for ESP32, pull-up resistors, and terminals. |
| **9** | **Wiring / Silicone Ribbon Cable** | 1 spool | 26 AWG or 28 AWG ultra-flexible stranded silicone wire (multi-colored) | Flexible finger routing without restricting hand movement. |

---

### 2. Glove & Mechanical Materials

| Item # | Material | Quantity | Notes |
| :--- | :--- | :--- | :--- |
| **10** | **Gloves** | 1 Pair | Breathable nylon, cycling, or cotton gloves with snug fit (Left & Right). Finger-less or full finger. |
| **11** | **Elastic Sleeves / Fabric Guides** | 10 strips | Sewn or glued along the dorsal side of each finger to hold flex sensors flat along finger joints. |
| **12** | **Velcro Straps** | 2 pairs | 2-inch wide wristbands to anchor perfboard, ESP32, and battery securely. |
| **13** | **Heat Shrink Tubing** | Assorted | 1.5mm, 3mm, 6mm heat shrink for insulating solder joints on flex sensor pins. |
| **14** | **3D Printed Enclosure (Optional)** | 2 sets | Lightweight PLA/PETG wrist casing for ESP32, battery, and MPU-9250. |

---

### 3. ESP32 Pin Selection Rules (Critical ESP32 Constraint)

> **IMPORTANT WARNING REGARDING ESP32 ADC CHANNELS:**  
> When the ESP32 Wi-Fi module is enabled, **ADC2 pins cannot be used** because the Wi-Fi driver uses the ADC2 SAR controller.  
> Therefore, **all 5 flex sensors must strictly be wired to ADC1 pins**!

#### ADC1 Pin Mapping (Identical on both Left & Right ESP32):
* **Thumb Flex:** `GPIO 36` (VP) - ADC1 Channel 0
* **Index Flex:** `GPIO 39` (VN) - ADC1 Channel 3
* **Middle Flex:** `GPIO 34` - ADC1 Channel 6
* **Ring Flex:** `GPIO 35` - ADC1 Channel 7
* **Pinky Flex:** `GPIO 32` - ADC1 Channel 4

#### MPU-9250 I2C Pin Mapping:
* **SDA (Data):** `GPIO 21`
* **SCL (Clock):** `GPIO 22`
* **VCC:** `3.3V` (clean regulated output from ESP32)
* **GND:** `GND`

---

### 4. Resistor Divider Sizing Calculation

The flex sensor acts as a variable resistor $R_{\text{flex}}$. In a voltage divider with a pull-down resistor $R_{\text{ref}}$:

$$V_{\text{out}} = V_{\text{cc}} \times \frac{R_{\text{ref}}}{R_{\text{flex}} + R_{\text{ref}}}$$

* Flat State ($R_{\text{flex}} \approx 10\text{ k}\Omega$):  
  With $R_{\text{ref}} = 22\text{ k}\Omega$ and $V_{\text{cc}} = 3.3\text{ V}$:
  $$V_{\text{flat}} = 3.3 \times \frac{22}{10 + 22} = 3.3 \times \frac{22}{32} \approx 2.26\text{ V}$$

* Bent State 90° ($R_{\text{flex}} \approx 60\text{ k}\Omega$):  
  $$V_{\text{bent}} = 3.3 \times \frac{22}{60 + 22} = 3.3 \times \frac{22}{82} \approx 0.88\text{ V}$$

* **Dynamic Range:** $2.26\text{ V} - 0.88\text{ V} \approx 1.38\text{ V}$, which corresponds to ~1700 ADC counts on ESP32 12-bit ADC (`0 - 4095`), giving crisp, high-resolution finger deflection measurement!

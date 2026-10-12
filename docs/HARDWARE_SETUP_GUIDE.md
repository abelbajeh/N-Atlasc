# Hardware Assembly & Physical Glove Fabrication Guide
## ASL to Nigerian Languages Translation System

This guide outlines step-by-step instructions to physically build, wire, mount, and calibrate both the Left and Right sensor gloves.

---

### Step 1: Preparing the Glove and Sensor Sleeves

1. **Glove Selection:**
   - Choose a snug-fitting, breathable glove (cotton, nylon, or spandex work best). The glove must fit tightly so that finger bending accurately strains the flex sensors without slack.
2. **Fabric Guide Pockets:**
   - Cut five 10–12 mm wide strips of elastic fabric or non-stretch fabric ribbons per glove.
   - Stitch or fabric-glue the strips along the dorsal (top) spine of each finger on the glove (Thumb, Index, Middle, Ring, Pinky).
   - Leave both ends open so the flex sensor can slide through, allowing the sensor to flex smoothly with the joint without buckling.
3. **Reinforce Flex Sensor Terminals (Crucial):**
   - The metal crimp terminals at the base of flex sensors are brittle and will snap under repetitive motion if not reinforced.
   - Solder flexible stranded 26/28 AWG wires to the sensor pins.
   - Apply heat-shrink tubing over each joint.
   - Coat the base crimp area with a drop of hot-melt adhesive or 5-minute epoxy for strain relief.

---

### Step 2: Wristband & Component Mounting

1. **Mounting Plate:**
   - Cut a small perfboard or 3D-print a lightweight wrist cradle ($40 \times 60 \text{ mm}$).
   - Fasten the perfboard onto a wide Velcro wrist strap.
2. **IMU Placement (MPU-9250):**
   - Mount the MPU-9250 module directly onto the flat dorsal surface of the hand (back of the palm or lower wrist plate).
   - Ensure the module is rigidly fixed (double-sided foam tape or screw mounts) so that palm rotations correspond 1:1 with IMU readings.
   - Align axes: $+Y$ axis facing forward toward the fingers, $+X$ pointing sideways, $+Z$ pointing upward.
3. **ESP32 & Battery Placement:**
   - Position the ESP32 dev board on the wristband perfboard.
   - Mount the TP4056 charging board and LiPo battery under/beside the ESP32.
   - Ensure the Micro-USB/USB-C charging port on the TP4056 and the ESP32 programming port remain accessible.

---

### Step 3: Wiring and Soldering

1. **Solder the Voltage Divider Matrix:**
   - On the perfboard, solder five 22 kΩ resistors with one side tied to a common `GND` rail.
   - Connect the other side of each resistor to the respective ESP32 ADC pin (`GPIO 36, 39, 34, 35, 32`).
   - Solder a $0.1\,\mu\text{F}$ noise capacitor in parallel with each 22 kΩ resistor (between ADC pin and GND).
2. **Connect the Flex Sensors:**
   - Run one wire from each flex sensor to the `+3.3V` regulated rail on the ESP32.
   - Run the second wire of each flex sensor to the corresponding ADC node (junction above the 22 kΩ resistor).
3. **Connect the MPU-9250:**
   - Connect `VCC` to `3.3V`.
   - Connect `GND` to `GND`.
   - Connect `SDA` to `GPIO 21`.
   - Connect `SCL` to `GPIO 22`.
   - Connect `AD0` to `GND` (sets I2C address to `0x68`).

---

### Step 4: Verification & Smoke Test Checklist

Before putting the gloves on:
- [ ] **Continuity & Short-Circuit Check:** Use a multimeter in continuity mode to ensure no short circuit between `3.3V` and `GND`.
- [ ] **Power Supply Check:** Power on the TP4056 switch; verify the ESP32 power LED illuminates and outputs $3.30 \pm 0.05 \text{ V}$ on the 3.3V pin.
- [ ] **I2C Bus Scan:** Flash a simple I2C scanner sketch to verify MPU-9250 responds on address `0x68`.
- [ ] **ADC Range Test:** Read raw ADC values on the 5 flex channels. Flat hand should report ~2500–3100 counts; a 90° bend should drop to ~1000–1600 counts.

---

### Step 5: Physical Calibration Protocol

Once the gloves are assembled and donned:
1. **Flat Hand Baseline (Zero Degree Bend):**
   - Place both hands completely flat on a table, fingers straight.
   - Capture min/max raw ADC values (recorded as $ADC_{\text{flat}}$).
2. **Closed Fist Calibration (Max Degree Bend):**
   - Make a firm fist with all five fingers tightly curled.
   - Capture raw ADC values (recorded as $ADC_{\text{bent}}$).
3. **IMU Neutral Orientation:**
   - Rest hands flat on the desk, palms down, pointing forward.
   - Zero out the gyroscope offset and set reference pitch/roll angles.
4. **Firmware / GUI Calibration Storage:**
   - These calibration values are saved directly into the Python GUI calibration profile or flashed to ESP32 EEPROM/NVS for automatic normalization ($0.0 = \text{straight}$, $1.0 = \text{fully bent}$).

---

### Step 6: Inbuilt Status LED Diagnostics (GPIO 2)

Each ESP32's onboard LED visually communicates its operational and networking status:

| LED State | Hardware Meaning | Action Required |
| :--- | :--- | :--- |
| **Rapid Blinking (150ms)** | Disconnected / Searching for Wi-Fi | Check SSID/password or router 2.4 GHz status |
| **Solid Blue (Constant ON)** | Connected to Wi-Fi & Streaming Telemetry | Ready for gesture recognition in GUI |
| **Double Pulse Flash** | Received UDP Ping from Python App | Network handshake verified |
| **5 Rapid Flashes** | Physical Glove Identification Probe | Triggered via GUI `[Flash LED]` button |


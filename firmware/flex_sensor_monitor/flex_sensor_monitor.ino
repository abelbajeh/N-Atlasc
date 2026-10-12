/**
 * ==============================================================================
 * Project: N-Atlas ASL Dual-Glove Translation System
 * File:    firmware/flex_sensor_monitor/flex_sensor_monitor.ino
 * Purpose: Real-Time Flex Sensor ADC Monitor & Glove Calibration Utility
 * ==============================================================================
 * 
 * HARDWARE PIN CONNECTIONS (Strictly ADC1 pins to ensure Wi-Fi compatibility):
 * ------------------------------------------------------------------------------
 * Finger      ESP32 GPIO Pin    ADC Channel    Circuit
 * ------------------------------------------------------------------------------
 * 1. Thumb    GPIO 36 (VP/SVP)  ADC1_CH0       3.3V -> Flex -> Pin -> 22kΩ -> GND
 * 2. Index    GPIO 39 (VN/SVN)  ADC1_CH3       3.3V -> Flex -> Pin -> 22kΩ -> GND
 * 3. Middle   GPIO 34           ADC1_CH6       3.3V -> Flex -> Pin -> 22kΩ -> GND
 * 4. Ring     GPIO 35           ADC1_CH7       3.3V -> Flex -> Pin -> 22kΩ -> GND
 * 5. Pinky    GPIO 32           ADC1_CH4       3.3V -> Flex -> Pin -> 22kΩ -> GND
 * 
 * Onboard LED: GPIO 2 (Heartbeat / Activity indicator)
 * Baud Rate:   115200 bps
 * 
 * INTERACTIVE SERIAL COMMANDS (Send single character via Serial Monitor):
 * ------------------------------------------------------------------------------
 *  'm' or 't' : Switch to Tabular Dashboard Mode (Human-readable table)
 *  'p'        : Switch to Arduino Serial Plotter Mode (Live waveform graphs)
 *  'j'        : Switch to JSON Stream Mode (Compatible with N-Atlas Python app)
 *  'c'        : Print Calibration Profile (Ready to paste into glove_calibration.json)
 *  'r'        : Reset Min/Max calibration tracking counters
 *  'h' or '?' : Display Help menu
 * ==============================================================================
 */

#include <Arduino.h>

// ------------------------------------------------------------------------------
// Pin Definitions (Matches N-Atlas Circuit Diagram & config.h)
// ------------------------------------------------------------------------------
#define NUM_SENSORS        5

#define PIN_FLEX_THUMB     36   // ADC1_CH0
#define PIN_FLEX_INDEX     39   // ADC1_CH3
#define PIN_FLEX_MIDDLE    34   // ADC1_CH6
#define PIN_FLEX_RING      35   // ADC1_CH7
#define PIN_FLEX_PINKY     32   // ADC1_CH4

#define PIN_STATUS_LED     2    // ESP32 Onboard Blue LED

// ------------------------------------------------------------------------------
// Sensor Metadata & Sampling Parameters
// ------------------------------------------------------------------------------
const uint8_t SENSOR_PINS[NUM_SENSORS] = {
    PIN_FLEX_THUMB,
    PIN_FLEX_INDEX,
    PIN_FLEX_MIDDLE,
    PIN_FLEX_RING,
    PIN_FLEX_PINKY
};

const char* SENSOR_NAMES[NUM_SENSORS] = {
    "THUMB ",
    "INDEX ",
    "MIDDLE",
    "RING  ",
    "PINKY "
};

// Oversampling to filter out high-frequency noise & ADC jitter
#define ADC_OVERSAMPLES    16
#define ADC_REF_VOLTAGE    3.3f
#define ADC_MAX_COUNT      4095.0f

// Operating Modes
enum DisplayMode {
    MODE_TABLE = 0,    // Formatted text table with ASCII bars
    MODE_PLOTTER = 1,  // Multi-curve Serial Plotter format
    MODE_JSON = 2      // Structured JSON packets
};

DisplayMode currentMode = MODE_TABLE;

// Live readings and calibration tracking
uint16_t currentRaw[NUM_SENSORS]  = {0};
float    currentVolt[NUM_SENSORS] = {0.0f};

uint16_t minRecorded[NUM_SENSORS];
uint16_t maxRecorded[NUM_SENSORS];

unsigned long lastPrintTime = 0;
const unsigned long TABLE_INTERVAL_MS   = 200; // 5 Hz refresh for readable text
const unsigned long PLOTTER_INTERVAL_MS = 25;  // 40 Hz refresh for smooth graphs
const unsigned long JSON_INTERVAL_MS    = 50;  // 20 Hz refresh for JSON stream

unsigned long sampleCount = 0;

// ==============================================================================
// Helper Functions
// ==============================================================================

/**
 * Resets recorded min/max values to initial state.
 */
void resetCalibrationStats() {
    for (int i = 0; i < NUM_SENSORS; i++) {
        minRecorded[i] = 4095;
        maxRecorded[i] = 0;
    }
    sampleCount = 0;
    Serial.println("\n[CALIBRATION] Min/Max stats reset! Move fingers through full range.\n");
}

/**
 * Reads sensor with oversampling and anti-jitter averaging.
 */
uint16_t readFilteredADC(uint8_t pin) {
    uint32_t sum = 0;
    for (int i = 0; i < ADC_OVERSAMPLES; i++) {
        sum += analogRead(pin);
        delayMicroseconds(25);
    }
    return (uint16_t)(sum / ADC_OVERSAMPLES);
}

/**
 * Updates readings and tracks min/max extremes.
 */
void acquireSensors() {
    for (int i = 0; i < NUM_SENSORS; i++) {
        uint16_t raw = readFilteredADC(SENSOR_PINS[i]);
        currentRaw[i] = raw;
        currentVolt[i] = (raw / ADC_MAX_COUNT) * ADC_REF_VOLTAGE;

        if (raw < minRecorded[i]) minRecorded[i] = raw;
        if (raw > maxRecorded[i]) maxRecorded[i] = raw;
    }
    sampleCount++;
}

/**
 * Generates an ASCII progress bar representing the ADC reading or bend percentage.
 */
void renderBar(char* outBuffer, size_t outSize, uint16_t val, uint16_t minVal, uint16_t maxVal, int barWidth = 14) {
    if (outSize < (size_t)(barWidth + 3)) return;
    
    // Normalized position (0.0 to 1.0)
    float ratio = 0.0f;
    if (maxVal > minVal) {
        ratio = (float)(val - minVal) / (float)(maxVal - minVal);
    } else {
        ratio = (float)val / ADC_MAX_COUNT;
    }
    if (ratio < 0.0f) ratio = 0.0f;
    if (ratio > 1.0f) ratio = 1.0f;

    int filled = (int)(ratio * barWidth);
    outBuffer[0] = '[';
    for (int i = 0; i < barWidth; i++) {
        outBuffer[1 + i] = (i < filled) ? '#' : '-';
    }
    outBuffer[1 + barWidth] = ']';
    outBuffer[2 + barWidth] = '\0';
}

/**
 * Prints the Interactive Command Menu.
 */
void printHelpMenu() {
    Serial.println("\n========================================================");
    Serial.println("         N-ATLAS FLEX SENSOR MONITOR - COMMANDS         ");
    Serial.println("========================================================");
    Serial.println("  [m] or [t] -> Tabular Dashboard Mode (Terminal Table)");
    Serial.println("  [p]        -> Arduino Serial Plotter Mode (Live Curves)");
    Serial.println("  [j]        -> JSON Streaming Mode");
    Serial.println("  [c]        -> Print Calibration JSON for N-Atlas");
    Serial.println("  [r]        -> Reset Min/Max Calibration Stats");
    Serial.println("  [h] or [?] -> Show this Help Menu");
    Serial.println("========================================================\n");
}

/**
 * Prints Calibration JSON ready to be copied into glove_calibration.json.
 */
void printCalibrationSummary() {
    Serial.println("\n========================================================");
    Serial.println("      N-ATLAS GLOVE CALIBRATION PROFILE (JSON)         ");
    Serial.println("========================================================");
    Serial.println("// Copy the following values into data/calibration/glove_calibration.json");
    Serial.println("// (Note: With 22k pull-down to GND, flat hand produces HIGHER ADC,");
    Serial.println("//        bent finger produces LOWER ADC as flex resistance increases)");
    Serial.println("{");
    Serial.print("  \"flex_flat\": [");
    for (int i = 0; i < NUM_SENSORS; i++) {
        Serial.print(maxRecorded[i]);
        if (i < NUM_SENSORS - 1) Serial.print(", ");
    }
    Serial.println("],");

    Serial.print("  \"flex_bent\": [");
    for (int i = 0; i < NUM_SENSORS; i++) {
        Serial.print(minRecorded[i]);
        if (i < NUM_SENSORS - 1) Serial.print(", ");
    }
    Serial.println("]");
    Serial.println("}");
    Serial.println("========================================================\n");
}

/**
 * Tabular Dashboard display for Serial Monitor.
 */
void displayTable() {
    // Print clear header
    Serial.println("\n--- [N-Atlas ESP32 Flex Monitor] ---------------------------------------------");
    Serial.println("Finger   | GPIO | Raw ADC | Volts |  Min ADC |  Max ADC |  Delta | Gauge Bar");
    Serial.println("---------+------+---------+-------+----------+----------+--------+----------------");

    char barBuf[20];
    for (int i = 0; i < NUM_SENSORS; i++) {
        uint16_t delta = (maxRecorded[i] > minRecorded[i]) ? (maxRecorded[i] - minRecorded[i]) : 0;
        renderBar(barBuf, sizeof(barBuf), currentRaw[i], minRecorded[i], maxRecorded[i], 12);

        Serial.printf("%s   |  %02d  |  %4u   | %1.2fV |   %4u   |   %4u   |  %4u  | %s\n",
            SENSOR_NAMES[i],
            SENSOR_PINS[i],
            currentRaw[i],
            currentVolt[i],
            minRecorded[i],
            maxRecorded[i],
            delta,
            barBuf
        );
    }
    Serial.printf("Samples: %lu | Mode: Table | Keys: [p] Plotter  [c] Calib JSON  [r] Reset\n", sampleCount);
}

/**
 * Real-time format for Arduino Serial Plotter (Tools -> Serial Plotter).
 */
void displayPlotter() {
    // Arduino IDE Serial Plotter recognizes "Label:Value Label2:Value2"
    Serial.printf("Thumb:%u Index:%u Middle:%u Ring:%u Pinky:%u\n",
        currentRaw[0],
        currentRaw[1],
        currentRaw[2],
        currentRaw[3],
        currentRaw[4]
    );
}

/**
 * Standard JSON packet format matching N-Atlas telemetry.
 */
void displayJSON() {
    Serial.printf("{\"type\":\"flex_monitor\",\"samples\":%lu,\"pins\":[36,39,34,35,32],\"raw\":[%u,%u,%u,%u,%u],\"volts\":[%1.2f,%1.2f,%1.2f,%1.2f,%1.2f]}\n",
        sampleCount,
        currentRaw[0], currentRaw[1], currentRaw[2], currentRaw[3], currentRaw[4],
        currentVolt[0], currentVolt[1], currentVolt[2], currentVolt[3], currentVolt[4]
    );
}

/**
 * Processes incoming single-character commands from Serial Monitor.
 */
void handleSerialCommands() {
    while (Serial.available() > 0) {
        char cmd = (char)Serial.read();
        if (cmd == '\r' || cmd == '\n' || cmd == ' ') continue;

        switch (cmd) {
            case 'm':
            case 't':
                currentMode = MODE_TABLE;
                Serial.println("\n>> Switched to Tabular Dashboard Mode.\n");
                break;
            case 'p':
                currentMode = MODE_PLOTTER;
                Serial.println("\n>> Switched to Serial Plotter Mode. Open Tools -> Serial Plotter.\n");
                break;
            case 'j':
                currentMode = MODE_JSON;
                Serial.println("\n>> Switched to JSON Stream Mode.\n");
                break;
            case 'c':
                printCalibrationSummary();
                break;
            case 'r':
                resetCalibrationStats();
                break;
            case 'h':
            case '?':
                printHelpMenu();
                break;
            default:
                Serial.printf("Unknown command: '%c'. Send 'h' for help menu.\n", cmd);
                break;
        }
    }
}

// ==============================================================================
// Arduino Setup & Main Loop
// ==============================================================================

void setup() {
    // 1. Initialize Serial communication
    Serial.begin(115200);
    delay(500); // Allow UART to stabilize

    // 2. Setup onboard LED
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, HIGH);

    // 3. Configure ESP32 ADC: 12-bit (0 - 4095) with 11dB attenuation (~0 - 3.3V)
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    // Configure individual pin modes
    for (int i = 0; i < NUM_SENSORS; i++) {
        pinMode(SENSOR_PINS[i], INPUT);
    }

    // 4. Reset tracking statistics
    resetCalibrationStats();

    // 5. Welcome Banner
    Serial.println("\n========================================================");
    Serial.println("    N-ATLAS ASL DUAL-GLOVE FLEX SENSOR MONITOR          ");
    Serial.println("========================================================");
    Serial.println("  Thumb:   GPIO 36 (ADC1_CH0 - VP)");
    Serial.println("  Index:   GPIO 39 (ADC1_CH3 - VN)");
    Serial.println("  Middle:  GPIO 34 (ADC1_CH6)");
    Serial.println("  Ring:    GPIO 35 (ADC1_CH7)");
    Serial.println("  Pinky:   GPIO 32 (ADC1_CH4)");
    Serial.println("  Status:  12-bit ADC (0 - 4095), 16x Oversampling Active");
    Serial.println("========================================================");
    printHelpMenu();

    digitalWrite(PIN_STATUS_LED, LOW);
}

void loop() {
    // 1. Process any command entered into the Serial Monitor
    handleSerialCommands();

    // 2. Acquire filtered sensor values
    acquireSensors();

    // 3. Heartbeat toggle on Status LED (blinks gently to confirm active loop)
    static unsigned long lastBlink = 0;
    if (millis() - lastBlink > 500) {
        lastBlink = millis();
        digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
    }

    // 4. Output according to selected mode
    unsigned long now = millis();
    unsigned long interval = (currentMode == MODE_PLOTTER) ? PLOTTER_INTERVAL_MS :
                             (currentMode == MODE_JSON)    ? JSON_INTERVAL_MS :
                                                             TABLE_INTERVAL_MS;

    if (now - lastPrintTime >= interval) {
        lastPrintTime = now;
        switch (currentMode) {
            case MODE_TABLE:
                displayTable();
                break;
            case MODE_PLOTTER:
                displayPlotter();
                break;
            case MODE_JSON:
                displayJSON();
                break;
        }
    }
}

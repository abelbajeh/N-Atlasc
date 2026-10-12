/**
 * @file esp32_glove_left.ino
 * @brief Left Hand ASL Glove Firmware for ESP32.
 * Reads 5 flex sensors (ADC1) and MPU-9250 9-DOF IMU, then streams
 * high-rate telemetry packets to the Python host over Wi-Fi UDP (or Bluetooth).
 */

#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "config.h"

#if !USE_WIFI_UDP
#include "BluetoothSerial.h"
BluetoothSerial SerialBT;
#endif

// UDP Client instance
WiFiUDP udp;
IPAddress targetHostIP(0, 0, 0, 0);
uint16_t targetHostPort = UDP_PORT;
bool isStreaming = false;

// Sensor variables
uint16_t flexRaw[5] = {0};
int16_t ax = 0, ay = 0, az = 0;
int16_t gx = 0, gy = 0, gz = 0;
int16_t mx = 0, my = 0, mz = 0;

unsigned long lastSampleTime = 0;
unsigned long packetCount = 0;

// ==========================================
// MPU-9250 Register Helpers
// ==========================================
#define MPU_PWR_MGMT_1   0x6B
#define MPU_ACCEL_XOUT_H 0x3B
#define MPU_GYRO_XOUT_H  0x43
#define MPU_INT_PIN_CFG  0x37
#define AK8963_ADDR      0x0C
#define AK8963_CNTL      0x0A
#define AK8963_HXL       0x03

void writeByte(uint8_t address, uint8_t subAddress, uint8_t data) {
    Wire.beginTransmission(address);
    Wire.write(subAddress);
    Wire.write(data);
    Wire.endTransmission();
}

bool initMPU9250() {
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000); // 400 kHz Fast I2C
    delay(20);

    // Wake up MPU-9250
    writeByte(MPU9250_I2C_ADDR, MPU_PWR_MGMT_1, 0x00);
    delay(10);

    // Enable I2C bypass multiplexer so ESP32 can talk directly to AK8963 Magnetometer
    writeByte(MPU9250_I2C_ADDR, MPU_INT_PIN_CFG, 0x02);
    delay(10);

    // Put AK8963 into Continuous measurement mode 2 (100 Hz, 16-bit)
    writeByte(AK8963_ADDR, AK8963_CNTL, 0x16);
    delay(10);

    Serial.println("[IMU] MPU-9250 & AK8963 initialized.");
    return true;
}

void readMPU9250() {
    // Read 14 bytes: Accel (6) + Temp (2) + Gyro (6)
    Wire.beginTransmission(MPU9250_I2C_ADDR);
    Wire.write(MPU_ACCEL_XOUT_H);
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)MPU9250_I2C_ADDR, (uint8_t)14);

    if (Wire.available() >= 14) {
        ax = (Wire.read() << 8) | Wire.read();
        ay = (Wire.read() << 8) | Wire.read();
        az = (Wire.read() << 8) | Wire.read();
        int16_t tempRaw = (Wire.read() << 8) | Wire.read(); (void)tempRaw;
        gx = (Wire.read() << 8) | Wire.read();
        gy = (Wire.read() << 8) | Wire.read();
        gz = (Wire.read() << 8) | Wire.read();
    }

    // Read Magnetometer (7 bytes: X, Y, Z + ST2 status register)
    Wire.beginTransmission(AK8963_ADDR);
    Wire.write(AK8963_HXL);
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)AK8963_ADDR, (uint8_t)7);

    if (Wire.available() >= 7) {
        uint8_t xl = Wire.read(); uint8_t xh = Wire.read();
        uint8_t yl = Wire.read(); uint8_t yh = Wire.read();
        uint8_t zl = Wire.read(); uint8_t zh = Wire.read();
        uint8_t st2 = Wire.read(); (void)st2;

        mx = (int16_t)(xh << 8 | xl);
        my = (int16_t)(yh << 8 | yl);
        mz = (int16_t)(zh << 8 | zl);
    }
}

// ==========================================
// Flex Sensor ADC Oversampling
// ==========================================
uint16_t readFilteredADC(uint8_t pin) {
    uint32_t sum = 0;
    for (int i = 0; i < ADC_OVERSAMPLES; i++) {
        sum += analogRead(pin);
        delayMicroseconds(20);
    }
    return (uint16_t)(sum / ADC_OVERSAMPLES);
}

void readAllFlexSensors() {
    flexRaw[0] = readFilteredADC(PIN_FLEX_THUMB);
    flexRaw[1] = readFilteredADC(PIN_FLEX_INDEX);
    flexRaw[2] = readFilteredADC(PIN_FLEX_MIDDLE);
    flexRaw[3] = readFilteredADC(PIN_FLEX_RING);
    flexRaw[4] = readFilteredADC(PIN_FLEX_PINKY);
}

// ==========================================
// Network Status & IP Display Banner
// ==========================================
void printNetworkStatusBanner() {
    Serial.println("\n========================================================");
    Serial.printf("  >>> %s GLOVE (ID: %d) READY <<<\n", HAND_NAME, HAND_ID);
    Serial.println("========================================================");
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("  GLOVE IP:    %s  <-- ENTER THIS IN PYTHON GUI\n", WiFi.localIP().toString().c_str());
        Serial.printf("  PORT:        %d\n", UDP_PORT);
        Serial.printf("  SSID:        %s (Signal: %d dBm)\n", WIFI_SSID, WiFi.RSSI());
        Serial.printf("  STATUS:      %s\n", isStreaming ? "STREAMING (Connected to GUI)" : "STANDBY (Waiting for Python GUI Connect button)");
        if (isStreaming) {
            Serial.printf("  STREAM DEST: %s:%d\n", targetHostIP.toString().c_str(), targetHostPort);
        }
        Serial.println("--------------------------------------------------------");
        Serial.println("  >>> IN PYTHON GUI:");
        Serial.printf("      1. Open GUI -> Enter '%s IP': %s\n", (HAND_ID == 0 ? "Left" : "Right"), WiFi.localIP().toString().c_str());
        Serial.println("      2. Click '🔗 Connect' button");
        Serial.println("      (Tip: Press ENTER in Serial Monitor to reprint this banner)");
        Serial.println("========================================================\n");
    } else {
        Serial.printf("  STATUS:      DISCONNECTED FROM WI-FI\n");
        Serial.printf("  SSID:        %s\n", WIFI_SSID);
        Serial.println("  Tip: Ensure your Wi-Fi router or laptop hotspot is active.");
        Serial.println("========================================================\n");
    }
}

void setupWiFi() {
    Serial.printf("\n[WIFI] Connecting to SSID: '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(250);
        digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        udp.begin(UDP_PORT);
        isStreaming = false; // Standby: Wait for user to click Connect in Python GUI
        printNetworkStatusBanner();
    } else {
        Serial.println("\n[WIFI] Connection failed! Check SSID/Password or router.");
    }
}

// ==========================================
// Setup & Main Loop
// ==========================================
void setup() {
    Serial.begin(115200);
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    // Configure 12-bit ADC attenuation (0 - 3.3V range)
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    Serial.printf("\n====================================\n");
    Serial.printf("  %s GLOVE - ASL TELEMETRY NODE\n", HAND_NAME);
    Serial.printf("====================================\n");

    // Initialize I2C IMU
    initMPU9250();

#if USE_WIFI_UDP
    setupWiFi();
#else
    SerialBT.begin(DEVICE_BT_NAME);
    Serial.printf("[BT] Bluetooth Serial Started as '%s'\n", DEVICE_BT_NAME);
#endif
}

// ==========================================
// Inbuilt LED Control & Incoming Command Handling
// ==========================================
void flashLED(int count, int delayMs) {
    for (int i = 0; i < count; i++) {
        digitalWrite(PIN_STATUS_LED, LOW);
        delay(delayMs);
        digitalWrite(PIN_STATUS_LED, HIGH);
        delay(delayMs);
    }
}

void checkIncomingUDP() {
#if USE_WIFI_UDP
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        char packetBuffer[256];
        int len = udp.read(packetBuffer, 255);
        if (len > 0) packetBuffer[len] = 0;

        IPAddress senderIP = udp.remoteIP();
        uint16_t senderPort = udp.remotePort();

        // 1. Connection Handshake from Python GUI
        if (strstr(packetBuffer, "CONNECT") != NULL) {
            targetHostIP = senderIP;
            targetHostPort = (senderPort > 0 && senderPort != 5005) ? senderPort : UDP_PORT;
            isStreaming = true; // Activate telemetry stream
            packetCount = 0;

            // Send handshake confirmation response
            char reply[200];
            snprintf(reply, sizeof(reply),
                "{\"hand\":\"%s\",\"cmd\":\"CONNECTED\",\"connected\":true,\"ip\":\"%s\",\"port\":%d,\"rssi\":%d}\n",
                HAND_NAME, WiFi.localIP().toString().c_str(), UDP_PORT, WiFi.RSSI());
            
            // Reply directly to sender IP on UDP_PORT (5005)
            udp.beginPacket(senderIP, UDP_PORT);
            udp.write((const uint8_t*)reply, strlen(reply));
            udp.endPacket();

            // If sender used an ephemeral port, also echo reply there
            if (senderPort != UDP_PORT && senderPort > 0) {
                udp.beginPacket(senderIP, senderPort);
                udp.write((const uint8_t*)reply, strlen(reply));
                udp.endPacket();
            }

            flashLED(2, 60);
            digitalWrite(PIN_STATUS_LED, HIGH); // Solid ON when actively streaming
            Serial.printf("[UDP] CONNECT received from Host PC (%s)! Telemetry stream ACTIVATED (50 Hz).\n",
                senderIP.toString().c_str());
        }
        // 2. Ping Check
        else if (strstr(packetBuffer, "PING") != NULL) {
            char reply[200];
            snprintf(reply, sizeof(reply),
                "{\"hand\":\"%s\",\"cmd\":\"PONG\",\"pong\":true,\"connected\":%s,\"ip\":\"%s\",\"rssi\":%d}\n",
                HAND_NAME, isStreaming ? "true" : "false", WiFi.localIP().toString().c_str(), WiFi.RSSI());
            udp.beginPacket(senderIP, UDP_PORT);
            udp.write((const uint8_t*)reply, strlen(reply));
            udp.endPacket();
            if (senderPort != UDP_PORT && senderPort > 0) {
                udp.beginPacket(senderIP, senderPort);
                udp.write((const uint8_t*)reply, strlen(reply));
                udp.endPacket();
            }
            flashLED(1, 50);
            Serial.printf("[UDP] PING from %s (Replied PONG)\n", senderIP.toString().c_str());
        }
        // 3. Disconnect Command from Python GUI
        else if (strstr(packetBuffer, "DISCONNECT") != NULL) {
            isStreaming = false; // Deactivate stream

            char reply[180];
            snprintf(reply, sizeof(reply),
                "{\"hand\":\"%s\",\"cmd\":\"DISCONNECTED\",\"connected\":false,\"ip\":\"%s\"}\n",
                HAND_NAME, WiFi.localIP().toString().c_str());
            udp.beginPacket(senderIP, UDP_PORT);
            udp.write((const uint8_t*)reply, strlen(reply));
            udp.endPacket();

            digitalWrite(PIN_STATUS_LED, LOW);
            Serial.printf("[UDP] DISCONNECT received from GUI (%s). Stream PAUSED. Standing by...\n",
                senderIP.toString().c_str());
        }
        // 4. LED Flash Command
        else if (strstr(packetBuffer, "BLINK") != NULL) {
            flashLED(5, 100);
            Serial.printf("[UDP] BLINK command from %s\n", senderIP.toString().c_str());
        }
    }
#endif
}

void checkSerialInput() {
    if (Serial.available() > 0) {
        while (Serial.available() > 0) Serial.read(); // flush buffer
        printNetworkStatusBanner();
    }
}

void loop() {
    unsigned long now = millis();

    // Check for interactive Serial input (hitting Enter reprints IP banner)
    checkSerialInput();

    // Manage Status LED & UDP Commands
#if USE_WIFI_UDP
    if (WiFi.status() == WL_CONNECTED) {
        checkIncomingUDP();
        if (isStreaming) {
            digitalWrite(PIN_STATUS_LED, HIGH); // Solid ON while streaming
        } else {
            // Gentle standby blink (500ms cycle) while waiting for GUI
            static unsigned long lastBlink = 0;
            if (now - lastBlink >= 500) {
                lastBlink = now;
                digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
            }
        }
    } else {
        // Fast blink when disconnected from Wi-Fi
        static unsigned long lastWifiBlink = 0;
        if (now - lastWifiBlink >= 150) {
            lastWifiBlink = now;
            digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
        }
    }
#endif

    // Periodic reminder on Serial Monitor every 5 seconds
    static unsigned long lastIpPrintTime = 0;
    if (now - lastIpPrintTime >= 5000) {
        lastIpPrintTime = now;
        if (WiFi.status() == WL_CONNECTED) {
            if (isStreaming) {
                Serial.printf("[%s GLOVE] Streaming to %s:%d | Pkts: %lu | RSSI: %d dBm\n",
                    HAND_NAME, targetHostIP.toString().c_str(), targetHostPort, packetCount, WiFi.RSSI());
            } else {
                Serial.printf("[%s GLOVE] STANDBY: IP: %s | Port: %d | Waiting for GUI Connect button...\n",
                    HAND_NAME, WiFi.localIP().toString().c_str(), UDP_PORT);
            }
        } else {
            Serial.printf("[%s GLOVE] Wi-Fi reconnecting to '%s'...\n", HAND_NAME, WIFI_SSID);
            WiFi.reconnect();
        }
    }

    // ONLY ACQUIRE AND TRANSMIT TELEMETRY IF isStreaming IS TRUE!
    if (isStreaming && (now - lastSampleTime >= SAMPLE_INTERVAL_MS)) {
        lastSampleTime = now;

        // 1. Acquire sensor readings
        readAllFlexSensors();
        readMPU9250();

        // 2. Format JSON Packet
        char buffer[360];
        snprintf(buffer, sizeof(buffer),
            "{\"hand\":\"%s\",\"id\":%d,\"ip\":\"%s\",\"ts\":%lu,\"seq\":%lu,"
            "\"flex\":[%u,%u,%u,%u,%u],"
            "\"accel\":[%d,%d,%d],"
            "\"gyro\":[%d,%d,%d],"
            "\"mag\":[%d,%d,%d]}\n",
            HAND_NAME, HAND_ID, WiFi.localIP().toString().c_str(), now, packetCount++,
            flexRaw[0], flexRaw[1], flexRaw[2], flexRaw[3], flexRaw[4],
            ax, ay, az,
            gx, gy, gz,
            mx, my, mz
        );

        // 3. Transmit packet directly to Python Host
#if USE_WIFI_UDP
        if (targetHostIP != IPAddress(0, 0, 0, 0)) {
            udp.beginPacket(targetHostIP, targetHostPort);
            udp.write((const uint8_t*)buffer, strlen(buffer));
            udp.endPacket();
        }
#else
        SerialBT.print(buffer);
#endif

        if (packetCount % 50 == 0) {
            Serial.print(buffer);
        }
    }
}



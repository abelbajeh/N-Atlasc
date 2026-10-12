#ifndef GLOVE_PACKET_H
#define GLOVE_PACKET_H

#include <stdint.h>

/**
 * @file GlovePacket.h
 * @brief Common packet definitions for ASL Smart Glove telemetry.
 *
 * Defines the binary struct and JSON protocol used by both Left and Right
 * ESP32 gloves to transmit sensor states over Wi-Fi UDP or Bluetooth.
 */

#pragma pack(push, 1)
struct GloveBinaryPacket {
    uint8_t  magicHeader[2];  // 0xAA, 0x55
    uint8_t  handId;          // 0 = LEFT, 1 = RIGHT
    uint32_t timestampMs;     // Millis timestamp on ESP32
    
    // 5 Flex Sensors (Normalized 12-bit ADC raw: 0 - 4095)
    uint16_t flex[5];         // Thumb, Index, Middle, Ring, Pinky
    
    // MPU-9250 IMU Data (Raw 16-bit integer values)
    int16_t  accel[3];        // Ax, Ay, Az
    int16_t  gyro[3];         // Gx, Gy, Gz
    int16_t  mag[3];          // Mx, My, Mz
    
    uint8_t  batteryPercent;  // Estimated 0 - 100%
    uint8_t  checksum;        // XOR checksum of packet body
};
#pragma pack(pop)

#define GLOVE_MAGIC_0 0xAA
#define GLOVE_MAGIC_1 0x55

#define HAND_LEFT  0
#define HAND_RIGHT 1

#endif // GLOVE_PACKET_H

/**
 * Simple ESP32 Flex Sensor Test on SVP Pin (GPIO 36)
 * 
 * Circuit Wiring:
 *   3.3V -----[ Flex Sensor ]-----+-----[ 22kΩ Resistor ]----- GND
 *                                 |
 *                             SVP (GPIO 36)
 */

const int FLEX_PIN = 36; // SVP pin is GPIO 36 (ADC1_CH0)

void setup() {
  Serial.begin(115200);
  delay(500);

  // Configure 12-bit ADC (values from 0 to 4095)
  analogReadResolution(12);

  // Set attenuation to 11dB to read full 0V - 3.3V range
  analogSetAttenuation(ADC_11db);

  Serial.println("\n--- ESP32 SVP Flex Sensor Test Started ---");
  Serial.println("Move/bend the sensor to see ADC values change.");
}

void loop() {
  // Read raw ADC value (0 - 4095)
  int rawADC = analogRead(FLEX_PIN);

  // Convert raw value to approximate voltage (0.0V - 3.3V)
  float voltage = (rawADC / 4095.0) * 3.3;

  // Print results to Serial Monitor
  Serial.print("SVP (GPIO 36) Raw ADC: ");
  Serial.print(rawADC);
  Serial.print("  |  Voltage: ");
  Serial.print(voltage, 2);
  Serial.println(" V");

  delay(150); // Read ~6-7 times per second
}

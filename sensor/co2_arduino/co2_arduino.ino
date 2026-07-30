/*
 * co2_serial.ino — SCD41 CO2 sensor driver for Arduino Nano 33 BLE Sense Rev2
 *
 * Board  : Arduino Nano 33 BLE Sense Rev2
 * Sensor : DFRobot SCD41 (SEN0536), I2C 0x62
 * Wiring : SDA → A4, SCL → A5, VCC → 3.3 V, GND → GND
 * Baud   : 115200
 *
 * Outputs one JSON line every 5 s:
 *   {"message_type":"environment","device_id":"scd41-nano-01",
 *    "uptime_ms":5000,"co2_ppm":491,"temperature_c":23.60,"humidity_percent":37.90}
 */

#include <Wire.h>

static const uint8_t  SCD41_ADDR         = 0x62;
static const uint16_t CMD_STOP_PERIODIC  = 0x3F86;
static const uint16_t CMD_START_PERIODIC = 0x21B1;
static const uint16_t CMD_DATA_READY     = 0xE4B8;
static const uint16_t CMD_READ_MEAS      = 0xEC05;

static const char*    DEVICE_ID          = "scd41-nano-01";
static const uint32_t INTERVAL_MS        = 5000;

static uint8_t crc8(uint8_t a, uint8_t b) {
  uint8_t crc = 0xFF;
  uint8_t data[2] = {a, b};
  for (int i = 0; i < 2; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++)
      crc = (crc & 0x80) ? ((crc << 1) ^ 0x31) : (crc << 1);
  }
  return crc;
}

static void writeCmd(uint16_t cmd) {
  Wire.beginTransmission(SCD41_ADDR);
  Wire.write(cmd >> 8);
  Wire.write(cmd & 0xFF);
  Wire.endTransmission();
}

static bool readWords(uint16_t cmd, uint16_t* out, int n) {
  writeCmd(cmd);
  delay(1);
  Wire.requestFrom((uint8_t)SCD41_ADDR, (uint8_t)(n * 3));
  if (Wire.available() < n * 3) return false;
  for (int i = 0; i < n; i++) {
    uint8_t msb = Wire.read(), lsb = Wire.read(), crc = Wire.read();
    if (crc != crc8(msb, lsb)) return false;
    out[i] = ((uint16_t)msb << 8) | lsb;
  }
  return true;
}

static bool dataReady() {
  uint16_t w;
  return readWords(CMD_DATA_READY, &w, 1) && (w & 0x07FF);
}

static bool readMeasurement(uint16_t& co2, float& temp, float& hum) {
  uint16_t w[3];
  if (!readWords(CMD_READ_MEAS, w, 3)) return false;
  co2  = w[0];
  temp = -45.0f + 175.0f * w[1] / 65535.0f;
  hum  = 100.0f * w[2] / 65535.0f;
  return true;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Wire.begin();
  writeCmd(CMD_STOP_PERIODIC);
  delay(500);
  writeCmd(CMD_START_PERIODIC);
  delay(INTERVAL_MS);
}

void loop() {
  if (!dataReady()) { delay(500); return; }

  uint16_t co2;
  float temp, hum;
  if (!readMeasurement(co2, temp, hum) || co2 == 0) { delay(1000); return; }

  Serial.print("{\"message_type\":\"environment\",\"device_id\":\"");
  Serial.print(DEVICE_ID);
  Serial.print("\",\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",\"co2_ppm\":");
  Serial.print(co2);
  Serial.print(",\"temperature_c\":");
  Serial.print(temp, 2);
  Serial.print(",\"humidity_percent\":");
  Serial.print(hum, 2);
  Serial.println("}");

  delay(INTERVAL_MS);
}

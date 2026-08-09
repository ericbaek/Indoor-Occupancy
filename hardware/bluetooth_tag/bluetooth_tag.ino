// Broadcast ROOM-TAG-01 as a non-connectable BLE advertisement every 200 ms.

#include <ArduinoBLE.h>

// Tag IDs must begin with ROOM-TAG-.
static const char* TAG_ID = "ROOM-TAG-01";

static const int ADV_INTERVAL_MS = 200;

void setup() {
  Serial.begin(9600);

  // Allow the serial monitor up to three seconds to connect.
  unsigned long t = millis();
  while (!Serial && millis() - t < 3000) {
    ;
  }

  Serial.println("===========================================");
  Serial.print  ("  BLE Tag Firmware starting: ");
  Serial.println(TAG_ID);
  Serial.println("===========================================");

  if (!BLE.begin()) {
    Serial.println("ERROR: BLE initialisation failed. Halting.");
    // Flash the built-in LED when BLE initialisation fails.
    pinMode(LED_BUILTIN, OUTPUT);
    while (true) {
      digitalWrite(LED_BUILTIN, HIGH); delay(100);
      digitalWrite(LED_BUILTIN, LOW);  delay(100);
    }
  }

  BLE.setLocalName(TAG_ID);

  // ArduinoBLE uses 0.625 ms advertising units.
  BLE.setAdvertisingInterval(320);

  BLE.advertise();

  Serial.print("Broadcasting '");
  Serial.print(TAG_ID);
  Serial.print("' every ~");
  Serial.print(ADV_INTERVAL_MS);
  Serial.println(" ms. Tag is active.");
  Serial.println("Unplug from PC and attach a USB power bank to carry.");
}

void loop() {
  BLE.poll();
  delay(100);
}

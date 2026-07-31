/**
 * ROOM-TAG-01 BLE Advertiser
 *
 * Broadcasts a non-connectable BLE advertisement (ROOM-TAG-01) every 200ms.
 */

#include <ArduinoBLE.h>

// ── Change this to set the tag ID ──────────────────────────────────────────
// Must begin with "ROOM-TAG-" to be accepted by the backend scanner.
static const char* TAG_ID = "ROOM-TAG-01";

// Advertising interval in milliseconds (≈ 200 ms)
static const int ADV_INTERVAL_MS = 200;

void setup() {
  Serial.begin(9600);

  // Wait up to 3 seconds for the Serial Monitor (optional).
  // Remove this loop if running on battery with no PC attached.
  unsigned long t = millis();
  while (!Serial && millis() - t < 3000) {
    ; // wait
  }

  Serial.println("===========================================");
  Serial.print  ("  BLE Tag Firmware starting: ");
  Serial.println(TAG_ID);
  Serial.println("===========================================");

  // Initialise the BLE radio
  if (!BLE.begin()) {
    Serial.println("ERROR: BLE initialisation failed. Halting.");
    // Blink the built-in LED rapidly to signal a hardware error.
    pinMode(LED_BUILTIN, OUTPUT);
    while (true) {
      digitalWrite(LED_BUILTIN, HIGH); delay(100);
      digitalWrite(LED_BUILTIN, LOW);  delay(100);
    }
  }

  // Set the advertised local name — this is what the anchors filter on.
  BLE.setLocalName(TAG_ID);

  // Do NOT set any services or characteristics; we only advertise anonymously.

  // Set advertising interval (ArduinoBLE uses units of 0.625 ms).
  // 200 ms / 0.625 ms = 320 units.
  BLE.setAdvertisingInterval(320);

  // Start non-connectable advertising.
  // advertise() broadcasts both the advertising packet and scan response.
  BLE.advertise();

  Serial.print("Broadcasting '");
  Serial.print(TAG_ID);
  Serial.print("' every ~");
  Serial.print(ADV_INTERVAL_MS);
  Serial.println(" ms. Tag is active.");
  Serial.println("Unplug from PC and attach a USB power bank to carry.");
}

void loop() {
  // poll() allows the BLE stack to process events (keeps the radio alive).
  BLE.poll();

  // Nothing else to do — the tag only advertises passively.
  delay(100);
}

/**
 * ROOM-TAG-01 BLE Advertiser
 * ===========================
 * Arduino sketch for the Arduino Nano 33 BLE or Nano 33 BLE Sense Rev2.
 *
 * The board continuously broadcasts a non-connectable BLE advertisement
 * containing the Complete Local Name "ROOM-TAG-01".
 * Three fixed Windows laptops (anchors) scan for this advertisement and
 * measure RSSI to estimate the tag's position.
 *
 * The tag:
 *   - never connects to any device
 *   - never contacts the backend directly
 *   - broadcasts approximately every 200 ms
 *   - only identifies itself with an anonymous tag ID
 *
 * ─── How to change the tag ID ───────────────────────────────────────────────
 *   Edit the TAG_ID string below and re-upload the sketch.
 *   The tag ID must begin with "ROOM-TAG-" for the backend to accept it.
 *   Example: "ROOM-TAG-02" for a second participant.
 *
 * ─── How to upload ──────────────────────────────────────────────────────────
 *   1. Install the Arduino IDE (https://www.arduino.cc/en/software).
 *   2. In Arduino IDE: Tools > Board > Arduino Mbed OS Nano Boards >
 *      "Arduino Nano 33 BLE".
 *   3. Install ArduinoBLE library: Sketch > Include Library >
 *      Manage Libraries > search "ArduinoBLE" > Install.
 *   4. Open this file in Arduino IDE.
 *   5. Select the correct COM port: Tools > Port.
 *   6. Click Upload (→ button). The sketch compiles and flashes automatically.
 *   7. Open Serial Monitor (baud 115200) to see startup messages.
 *   8. Disconnect from the computer and attach a USB power bank.
 *      The sketch runs automatically on power-up without needing a PC.
 *
 * ─── Dependencies ────────────────────────────────────────────────────────────
 *   ArduinoBLE  (install via Arduino Library Manager)
 *
 * ─── Privacy note ────────────────────────────────────────────────────────────
 *   This device only advertises the anonymous tag ID above.
 *   No participant name, location, or personal data is embedded in the
 *   advertisement. The receiving laptops record only the tag ID and RSSI.
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

#!/usr/bin/env swift

// Advertise this Mac as a stable COMP6733 BLE participant.
//
// Apple CoreBluetooth advertising supports a local name and service UUIDs,
// rather than the manufacturer-data publisher used by the Windows helper.
// Keeping the name short and inside the existing ROOM-TAG-* namespace lets
// both Windows and macOS Bleak scanners derive the same stable device ID.

import CoreBluetooth
import Darwin
import Foundation

struct Options {
    let deviceToken: String
    let backendURL: URL?
    let coLocatedAnchor: String?
    let selfRSSI: Int

    var advertisedName: String { "ROOM-TAG-\(deviceToken)" }

    var serviceUUID: CBUUID {
        let tokenHex = deviceToken.utf8.map { String(format: "%02X", $0) }.joined()
        let padded = tokenHex.padding(toLength: 16, withPad: "0", startingAt: 0)
        let split = padded.index(padded.startIndex, offsetBy: 4)
        return CBUUID(
            string: "C6733033-4D41-4300-\(padded[..<split])-\(padded[split...])"
        )
    }
}

func usage(_ message: String? = nil) -> Never {
    if let message {
        FileHandle.standardError.write(Data("Error: \(message)\n".utf8))
    }
    let text = """
    Usage:
      swift ble_advertiser_macos.swift --device-id MAC1
      swift ble_advertiser_macos.swift --device-id LEFT \\
        --co-located-anchor anchor-left \\
        --backend-url http://127.0.0.1:5000/api/bluetooth/readings

    Options:
      --device-id ID              Unique 1-8 character ID (A-Z, 0-9, hyphen)
      --co-located-anchor SIDE    anchor-left or anchor-right
      --backend-url URL           Required with --co-located-anchor
      --self-rssi RSSI            Self heartbeat RSSI (default: -20)
    """
    FileHandle.standardError.write(Data("\(text)\n".utf8))
    exit(2)
}

func parseOptions() -> Options {
    let arguments = Array(CommandLine.arguments.dropFirst())
    var values: [String: String] = [:]
    var index = 0

    while index < arguments.count {
        let key = arguments[index]
        guard key.hasPrefix("--"), index + 1 < arguments.count else {
            usage("Every option must have a value")
        }
        values[key] = arguments[index + 1]
        index += 2
    }

    guard let rawDeviceID = values["--device-id"] else {
        usage("--device-id is required")
    }
    let token = rawDeviceID.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
    let allowed = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
    guard (1...8).contains(token.count), token.unicodeScalars.allSatisfy(allowed.contains) else {
        usage("--device-id must be 1-8 characters: A-Z, 0-9, or '-'")
    }

    let anchor = values["--co-located-anchor"]
    if let anchor, anchor != "anchor-left" && anchor != "anchor-right" {
        usage("--co-located-anchor must be anchor-left or anchor-right")
    }

    var backendURL: URL?
    if let rawURL = values["--backend-url"] {
        backendURL = URL(string: rawURL)
        if backendURL == nil {
            usage("--backend-url is not a valid URL")
        }
    }
    if anchor != nil && backendURL == nil {
        usage("--backend-url is required with --co-located-anchor")
    }

    let selfRSSI = Int(values["--self-rssi"] ?? "-20") ?? 1
    guard (-120...0).contains(selfRSSI) else {
        usage("--self-rssi must be between -120 and 0")
    }

    return Options(
        deviceToken: token,
        backendURL: backendURL,
        coLocatedAnchor: anchor,
        selfRSSI: selfRSSI
    )
}

final class MacBLEAdvertiser: NSObject, CBPeripheralManagerDelegate {
    private let options: Options
    private var manager: CBPeripheralManager!
    private var heartbeatTimer: Timer?

    init(options: Options) {
        self.options = options
        super.init()
        manager = CBPeripheralManager(delegate: self, queue: .main)
    }

    func peripheralManagerDidUpdateState(_ peripheral: CBPeripheralManager) {
        switch peripheral.state {
        case .poweredOn:
            print("Bluetooth is on; starting \(options.advertisedName) advertising...")
            peripheral.startAdvertising([
                CBAdvertisementDataLocalNameKey: options.advertisedName,
                CBAdvertisementDataServiceUUIDsKey: [options.serviceUUID]
            ])
        case .poweredOff:
            fail("Bluetooth is turned off in System Settings")
        case .unauthorized:
            fail("Bluetooth permission was denied. Enable it for Terminal in System Settings > Privacy & Security > Bluetooth")
        case .unsupported:
            fail("This Mac does not support BLE peripheral advertising")
        case .resetting:
            print("Bluetooth is resetting; waiting...")
        case .unknown:
            print("Bluetooth state is not ready; waiting...")
        @unknown default:
            fail("Unknown Bluetooth state: \(peripheral.state.rawValue)")
        }
    }

    func peripheralManagerDidStartAdvertising(
        _ peripheral: CBPeripheralManager,
        error: (any Error)?
    ) {
        if let error {
            fail("Bluetooth advertising failed: \(error.localizedDescription)")
        }
        guard peripheral.isAdvertising else {
            fail("CoreBluetooth did not enter advertising state")
        }

        print("Advertising actual Mac as \(options.advertisedName). Press Ctrl+C to stop.")
        if let anchor = options.coLocatedAnchor {
            print("Self-proximity heartbeat enabled for \(anchor).")
            postSelfReading()
            heartbeatTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) {
                [weak self] _ in self?.postSelfReading()
            }
        }
    }

    func stop() {
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil
        if manager.isAdvertising {
            manager.stopAdvertising()
        }
        print("Stopped Bluetooth advertising.")
    }

    private func postSelfReading() {
        guard manager.isAdvertising,
              let anchor = options.coLocatedAnchor,
              let backendURL = options.backendURL else { return }

        let payload: [String: Any] = [
            "message_type": "bluetooth_rssi",
            "scanner_id": anchor,
            "device_id": options.advertisedName,
            "device_name": "Bluetooth Mac \(options.deviceToken)",
            "rssi": options.selfRSSI,
            "tx_power": NSNull()
        ]

        guard let body = try? JSONSerialization.data(withJSONObject: payload) else {
            FileHandle.standardError.write(Data("Could not encode self reading\n".utf8))
            return
        }

        var request = URLRequest(url: backendURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        request.timeoutInterval = 3

        URLSession.shared.dataTask(with: request) { _, response, error in
            if let error {
                FileHandle.standardError.write(Data("Self reading failed: \(error.localizedDescription)\n".utf8))
                return
            }
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                FileHandle.standardError.write(Data("Self reading rejected: HTTP \(http.statusCode)\n".utf8))
            }
        }.resume()
    }

    private func fail(_ message: String) -> Never {
        FileHandle.standardError.write(Data("Cannot start Bluetooth advertiser: \(message)\n".utf8))
        exit(1)
    }
}

let options = parseOptions()
let advertiser = MacBLEAdvertiser(options: options)

signal(SIGINT, SIG_IGN)
signal(SIGTERM, SIG_IGN)

let interruptSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
interruptSource.setEventHandler {
    advertiser.stop()
    exit(0)
}
interruptSource.resume()

let terminateSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
terminateSource.setEventHandler {
    advertiser.stop()
    exit(0)
}
terminateSource.resume()

RunLoop.main.run()

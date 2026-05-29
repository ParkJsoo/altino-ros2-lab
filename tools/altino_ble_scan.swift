import Foundation
import CoreBluetooth

final class Scanner: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private var central: CBCentralManager!
    private var target: CBPeripheral?
    private var serviceCount = 0
    private var completedServices = Set<CBUUID>()

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: DispatchQueue.main)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        print("central state: \(stateName(central.state))")
        guard central.state == .poweredOn else { return }
        print("scanning...")
        central.scanForPeripherals(withServices: nil, options: [
            CBCentralManagerScanOptionAllowDuplicatesKey: false
        ])
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String : Any],
        rssi RSSI: NSNumber
    ) {
        let name = peripheral.name
            ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String
            ?? "<unnamed>"
        print("found name=\(name) id=\(peripheral.identifier.uuidString) rssi=\(RSSI)")

        guard target == nil, name.localizedCaseInsensitiveContains("ALTINO") else {
            return
        }

        target = peripheral
        peripheral.delegate = self
        central.stopScan()
        print("connecting \(name)...")
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("connected id=\(peripheral.identifier.uuidString)")
        peripheral.discoverServices(nil)
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        print("connect failed: \(error?.localizedDescription ?? "unknown")")
        exit(2)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error = error {
            print("discover services error: \(error.localizedDescription)")
            exit(3)
        }
        let services = peripheral.services ?? []
        serviceCount = services.count
        print("services count=\(services.count)")
        for service in services {
            print("service \(service.uuid.uuidString)")
            peripheral.discoverCharacteristics(nil, for: service)
        }
        if services.isEmpty { exit(0) }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error = error {
            print("discover characteristics error for \(service.uuid.uuidString): \(error.localizedDescription)")
        }
        for characteristic in service.characteristics ?? [] {
            print("  char \(characteristic.uuid.uuidString) props=\(props(characteristic.properties))")
        }
        completedServices.insert(service.uuid)
        if completedServices.count >= serviceCount {
            print("done")
            central.cancelPeripheralConnection(peripheral)
            exit(0)
        }
    }
}

private func stateName(_ state: CBManagerState) -> String {
    switch state {
    case .unknown: return "unknown"
    case .resetting: return "resetting"
    case .unsupported: return "unsupported"
    case .unauthorized: return "unauthorized"
    case .poweredOff: return "poweredOff"
    case .poweredOn: return "poweredOn"
    @unknown default: return "future"
    }
}

private func props(_ p: CBCharacteristicProperties) -> String {
    var names: [String] = []
    if p.contains(.broadcast) { names.append("broadcast") }
    if p.contains(.read) { names.append("read") }
    if p.contains(.writeWithoutResponse) { names.append("writeWithoutResponse") }
    if p.contains(.write) { names.append("write") }
    if p.contains(.notify) { names.append("notify") }
    if p.contains(.indicate) { names.append("indicate") }
    if p.contains(.authenticatedSignedWrites) { names.append("signedWrite") }
    if p.contains(.extendedProperties) { names.append("extended") }
    if p.contains(.notifyEncryptionRequired) { names.append("notifyEnc") }
    if p.contains(.indicateEncryptionRequired) { names.append("indicateEnc") }
    return names.joined(separator: "|")
}

let scanner = Scanner()
DispatchQueue.main.asyncAfter(deadline: .now() + 20) {
    print("timeout")
    exit(1)
}
RunLoop.main.run()

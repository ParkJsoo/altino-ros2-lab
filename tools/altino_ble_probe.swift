import Foundation
import CoreBluetooth

private let targetName = "ALTINO"
private let serviceUUID = CBUUID(string: "49535343-FE7D-4AE5-8FA9-9FAFD205E455")
private let notifyUUID = CBUUID(string: "49535343-1E4D-4BD9-BA61-23C647249616")
private let writeUUID = CBUUID(string: "49535343-8841-43F4-A8D4-ECBE34729BB3")

final class Probe: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private var central: CBCentralManager!
    private var target: CBPeripheral?
    private var writeChar: CBCharacteristic?
    private var notifyChar: CBCharacteristic?
    private var sent = false
    private var received = Data()

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: DispatchQueue.main)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        print("central state: \(stateName(central.state))")
        guard central.state == .poweredOn else { return }
        central.scanForPeripherals(withServices: [serviceUUID], options: nil)
        print("scanning for \(serviceUUID.uuidString)...")
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        let name = peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? "<unnamed>"
        print("found name=\(name) id=\(peripheral.identifier.uuidString) rssi=\(RSSI)")
        guard target == nil, name.localizedCaseInsensitiveContains(targetName) else { return }
        target = peripheral
        peripheral.delegate = self
        central.stopScan()
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("connected")
        print("max write withResponse=\(peripheral.maximumWriteValueLength(for: .withResponse)) withoutResponse=\(peripheral.maximumWriteValueLength(for: .withoutResponse))")
        peripheral.discoverServices([serviceUUID])
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error = error { print("service error: \(error.localizedDescription)"); exit(2) }
        for service in peripheral.services ?? [] {
            print("service \(service.uuid.uuidString)")
            peripheral.discoverCharacteristics([notifyUUID, writeUUID], for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error = error { print("char error: \(error.localizedDescription)") }
        for c in service.characteristics ?? [] {
            print("char \(c.uuid.uuidString) props=\(props(c.properties))")
            if c.uuid == writeUUID { writeChar = c }
            if c.uuid == notifyUUID { notifyChar = c }
        }
        if let n = notifyChar {
            peripheral.setNotifyValue(true, for: n)
        }
        maybeSend(on: peripheral)
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error { print("notify error: \(error.localizedDescription)") }
        print("notify \(characteristic.uuid.uuidString) isNotifying=\(characteristic.isNotifying)")
        maybeSend(on: peripheral)
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            print("write callback error: \(error.localizedDescription)")
        } else {
            print("write callback ok")
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error { print("rx error: \(error.localizedDescription)"); return }
        let data = characteristic.value ?? Data()
        received.append(data)
        print("rx chunk len=\(data.count) \(hex(data))")
    }

    private func maybeSend(on peripheral: CBPeripheral) {
        guard !sent, let w = writeChar else { return }
        if let n = notifyChar, !n.isNotifying { return }
        sent = true
        let packet = makeSafeSensorPacket()
        print("tx len=\(packet.count) \(hex(packet))")
        peripheral.writeValue(packet, for: w, type: .withResponse)
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            print("rx total len=\(self.received.count) \(hex(self.received))")
            self.central.cancelPeripheralConnection(peripheral)
            exit(self.received.isEmpty ? 1 : 0)
        }
    }
}

private func makeSafeSensorPacket() -> Data {
    var tx: [UInt8] = [2, 22, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3]
    tx[2] = UInt8(tx[3..<21].reduce(0) { Int($0) + Int($1) } % 256)
    return Data(tx)
}

private func hex(_ data: Data) -> String {
    data.map { String(format: "%02x", $0) }.joined(separator: " ")
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
    if p.contains(.read) { names.append("read") }
    if p.contains(.writeWithoutResponse) { names.append("writeWithoutResponse") }
    if p.contains(.write) { names.append("write") }
    if p.contains(.notify) { names.append("notify") }
    if p.contains(.indicate) { names.append("indicate") }
    return names.joined(separator: "|")
}

let probe = Probe()
DispatchQueue.main.asyncAfter(deadline: .now() + 15) {
    print("timeout")
    exit(9)
}
RunLoop.main.run()

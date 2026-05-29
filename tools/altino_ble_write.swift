import Foundation
import CoreBluetooth
import Darwin

private let targetName = "ALTINO"
private let serviceUUID = CBUUID(string: "49535343-FE7D-4AE5-8FA9-9FAFD205E455")
private let notifyUUID = CBUUID(string: "49535343-1E4D-4BD9-BA61-23C647249616")
private let writeUUID = CBUUID(string: "49535343-8841-43F4-A8D4-ECBE34729BB3")

private let maxDriveSpeed = 350
private let minDriveDuration = 0.05
private let maxDriveDuration = 3.0
private let stopBurstCount = 3
private let stopBurstInterval = 0.15
private let postCommandSettleTime = 0.8
private let postStopSettleTime = 0.5

private enum AppCommand: CustomStringConvertible {
    case scan(seconds: Double)
    case device(DeviceCommand)

    var description: String {
        switch self {
        case .scan(let seconds):
            return "scan seconds=\(formatSeconds(seconds))"
        case .device(let command):
            return command.description
        }
    }
}

private enum DeviceCommand: CustomStringConvertible {
    case light(on: Bool)
    case horn(on: Bool)
    case drive(left: Int, right: Int, duration: Double)
    case stop

    var description: String {
        switch self {
        case .light(let on):
            return "light \(on ? "on" : "off")"
        case .horn(let on):
            return "horn \(on ? "on" : "off")"
        case .drive(let left, let right, let duration):
            return "drive left=\(left) right=\(right) duration=\(formatSeconds(duration))"
        case .stop:
            return "stop"
        }
    }

    var timeoutSeconds: Double {
        switch self {
        case .drive(_, _, let duration):
            return duration + 12.0
        default:
            return 12.0
        }
    }
}

private final class Scanner: NSObject, CBCentralManagerDelegate {
    private let seconds: Double
    private var central: CBCentralManager!
    private var seen = Set<UUID>()

    init(seconds: Double) {
        self.seconds = seconds
        super.init()
        central = CBCentralManager(delegate: self, queue: DispatchQueue.main)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        print("central state: \(stateName(central.state))")
        guard central.state == .poweredOn else {
            if central.state == .unauthorized || central.state == .unsupported || central.state == .poweredOff {
                exitWithError("Bluetooth is not ready: \(stateName(central.state))", code: 2)
            }
            return
        }

        print("scanning seconds=\(formatSeconds(seconds))")
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
        guard seen.insert(peripheral.identifier).inserted else { return }

        let name = peripheralName(peripheral, advertisementData: advertisementData)
        let services = (advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID]) ?? []
        let serviceText = services.map { $0.uuidString }.joined(separator: ",")
        let isAltino = name.localizedCaseInsensitiveContains(targetName)
        let marker = isAltino ? " altino=yes" : ""
        print("found name=\(name) id=\(peripheral.identifier.uuidString) rssi=\(RSSI) services=[\(serviceText)]\(marker)")
    }

    func stopAndExit() {
        central.stopScan()
        print("scan complete")
        exit(0)
    }
}

private final class CommandRunner: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private let command: DeviceCommand
    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var writeChar: CBCharacteristic?
    private var notifyChar: CBCharacteristic?
    private var notifySettled = false
    private var started = false
    private var stopBurstStarted = false
    private var completed = false
    private var exitCode: Int32 = 0
    private var received = Data()

    init(command: DeviceCommand) {
        self.command = command
        super.init()
        central = CBCentralManager(delegate: self, queue: DispatchQueue.main)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        print("central state: \(stateName(central.state))")
        guard central.state == .poweredOn else {
            if central.state == .unauthorized || central.state == .unsupported || central.state == .poweredOff {
                exitWithError("Bluetooth is not ready: \(stateName(central.state))", code: 2)
            }
            return
        }

        print("scanning for \(targetName) service=\(serviceUUID.uuidString)")
        central.scanForPeripherals(withServices: [serviceUUID], options: nil)
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String : Any],
        rssi RSSI: NSNumber
    ) {
        let name = peripheralName(peripheral, advertisementData: advertisementData)
        print("found name=\(name) id=\(peripheral.identifier.uuidString) rssi=\(RSSI)")
        guard self.peripheral == nil, name.localizedCaseInsensitiveContains(targetName) else { return }

        self.peripheral = peripheral
        peripheral.delegate = self
        central.stopScan()
        print("connecting \(name)")
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("connected id=\(peripheral.identifier.uuidString)")
        print("max write withResponse=\(peripheral.maximumWriteValueLength(for: .withResponse)) withoutResponse=\(peripheral.maximumWriteValueLength(for: .withoutResponse))")
        peripheral.discoverServices([serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        exitWithError("connect failed: \(error?.localizedDescription ?? "unknown")", code: 3)
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        if completed {
            exit(exitCode)
        }

        let detail = error.map { ": \($0.localizedDescription)" } ?? ""
        exitWithError("disconnected before command completed\(detail)", code: 4)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error = error {
            exitWithError("service discovery failed: \(error.localizedDescription)", code: 5)
        }

        let services = peripheral.services ?? []
        guard !services.isEmpty else {
            exitWithError("Altino service not found", code: 5)
        }

        for service in services {
            print("service \(service.uuid.uuidString)")
            peripheral.discoverCharacteristics([notifyUUID, writeUUID], for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error = error {
            exitWithError("characteristic discovery failed: \(error.localizedDescription)", code: 6)
        }

        for characteristic in service.characteristics ?? [] {
            print("char \(characteristic.uuid.uuidString) props=\(props(characteristic.properties))")
            if characteristic.uuid == writeUUID {
                guard characteristic.properties.contains(.writeWithoutResponse) else {
                    exitWithError("write characteristic does not support writeWithoutResponse", code: 6)
                }
                writeChar = characteristic
            } else if characteristic.uuid == notifyUUID {
                notifyChar = characteristic
            }
        }

        guard writeChar != nil else {
            exitWithError("write characteristic not found", code: 6)
        }

        if let notifyChar {
            peripheral.setNotifyValue(true, for: notifyChar)
        } else {
            notifySettled = true
        }

        startIfReady()
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            print("notify setup failed: \(error.localizedDescription); continuing with writes")
        } else {
            print("notify \(characteristic.uuid.uuidString) isNotifying=\(characteristic.isNotifying)")
        }

        notifySettled = true
        startIfReady()
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            print("write callback error: \(error.localizedDescription)")
        } else {
            print("write callback ok")
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            print("rx error: \(error.localizedDescription)")
            return
        }

        let data = characteristic.value ?? Data()
        received.append(data)
        print("rx chunk len=\(data.count) \(hex(data))")
    }

    func timeoutStopAndExit() {
        guard !completed else { return }
        print("timeout; sending stop before exit if possible")
        sendStopBurst(reason: "timeout-stop") {
            self.finish(code: 9)
        }
    }

    func interruptStopAndExit(signalName: String) {
        guard !completed else { return }
        print("\(signalName); sending stop before exit if possible")
        sendStopBurst(reason: "interrupt-stop") {
            self.finish(code: 130)
        }
    }

    private func startIfReady() {
        guard !started, writeChar != nil, notifySettled else { return }
        started = true

        print("command=\(command)")
        switch command {
        case .light(let on):
            print("safe frame: motors=0 horn=off light=\(on ? "on" : "off")")
            writeAndroidPacket(androidPacket(light: on ? 0x01 : 0x00), label: on ? "light-on" : "light-off")
            finishAfter(postCommandSettleTime, code: 0)

        case .horn(let on):
            print("safe frame: motors=0 light=off horn=\(on ? "on" : "off")")
            writeAndroidPacket(androidPacket(sound: on ? 0x0f : 0x00), label: on ? "horn-on" : "horn-off")
            finishAfter(postCommandSettleTime, code: 0)

        case .stop:
            sendStopBurst(reason: "stop") {
                self.finish(code: 0)
            }

        case .drive(let left, let right, let duration):
            print("drive safety speed=0...\(maxDriveSpeed) maxDuration=\(formatSeconds(maxDriveDuration)) autoStop=burst")
            writeAndroidPacket(androidPacket(right: right, left: left), label: "drive")
            DispatchQueue.main.asyncAfter(deadline: .now() + duration) {
                self.sendStopBurst(reason: "auto-stop") {
                    self.finish(code: 0)
                }
            }
        }
    }

    private func finishAfter(_ delay: Double, code: Int32) {
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            self.finish(code: code)
        }
    }

    private func finish(code: Int32) {
        guard !completed else { return }
        completed = true
        exitCode = code

        if !received.isEmpty {
            print("rx total len=\(received.count) \(hex(received))")
        }

        if let peripheral {
            central.cancelPeripheralConnection(peripheral)
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                exit(code)
            }
        } else {
            exit(code)
        }
    }

    private func sendStopBurst(reason: String, completion: @escaping () -> Void) {
        let settleTime = Double(stopBurstCount - 1) * stopBurstInterval + postStopSettleTime

        guard !stopBurstStarted else {
            DispatchQueue.main.asyncAfter(deadline: .now() + settleTime) {
                completion()
            }
            return
        }

        stopBurstStarted = true
        for index in 0..<stopBurstCount {
            DispatchQueue.main.asyncAfter(deadline: .now() + Double(index) * stopBurstInterval) {
                self.writeAndroidPacket(androidPacket(), label: "\(reason)-\(index + 1)")
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + settleTime) {
            completion()
        }
    }

    private func writeAndroidPacket(_ packet: Data, label: String) {
        guard let peripheral, let writeChar else {
            print("tx \(label) not sent; BLE write characteristic is not ready")
            return
        }

        let bytes = [UInt8](packet)
        print("tx \(label) len=\(packet.count) \(hex(packet))")

        let split = min(14, bytes.count)
        for range in [0..<split, split..<bytes.count] where !range.isEmpty {
            let chunk = Data(bytes[range])
            print("  android chunk len=\(chunk.count) \(hex(chunk))")
            peripheral.writeValue(chunk, for: writeChar, type: .withoutResponse)
        }
    }
}

private func parseCommand() -> AppCommand {
    let args = Array(CommandLine.arguments.dropFirst())

    if args.isEmpty || args.contains("-h") || args.contains("--help") {
        printUsage()
        exit(args.isEmpty ? 64 : 0)
    }

    switch args[0] {
    case "scan":
        return .scan(seconds: parseScanSeconds(Array(args.dropFirst())))

    case "light":
        guard args.count == 2 else {
            exitWithUsage("light requires on or off")
        }
        return .device(.light(on: parseOnOff(args[1], label: "light")))

    case "horn":
        guard args.count == 2 else {
            exitWithUsage("horn requires on or off")
        }
        return .device(.horn(on: parseOnOff(args[1], label: "horn")))

    case "drive":
        guard args.count == 4 else {
            exitWithUsage("drive requires: <left-speed> <right-speed> <seconds>")
        }

        let left = parseInt(args[1], label: "left-speed")
        let right = parseInt(args[2], label: "right-speed")
        let duration = parseDouble(args[3], label: "seconds")
        validateDrive(left: left, right: right, duration: duration)
        return .device(.drive(left: left, right: right, duration: duration))

    case "stop":
        guard args.count == 1 else {
            exitWithUsage("stop does not accept arguments")
        }
        return .device(.stop)

    default:
        exitWithUsage("unknown command: \(args[0])")
    }
}

private func parseScanSeconds(_ args: [String]) -> Double {
    if args.isEmpty {
        return 8.0
    }

    guard args.count == 2, (args[0] == "--seconds" || args[0] == "-s") else {
        exitWithUsage("scan usage: scan [--seconds N]")
    }

    let seconds = parseDouble(args[1], label: "scan seconds")
    guard seconds >= 1.0 && seconds <= 30.0 else {
        exitWithUsage("scan seconds must be between 1 and 30")
    }
    return seconds
}

private func parseOnOff(_ value: String, label: String) -> Bool {
    switch value.lowercased() {
    case "on":
        return true
    case "off":
        return false
    default:
        exitWithUsage("\(label) value must be on or off")
    }
}

private func parseInt(_ value: String, label: String) -> Int {
    guard let number = Int(value) else {
        exitWithUsage("\(label) must be an integer")
    }
    return number
}

private func parseDouble(_ value: String, label: String) -> Double {
    guard let number = Double(value), number.isFinite else {
        exitWithUsage("\(label) must be a number")
    }
    return number
}

private func validateDrive(left: Int, right: Int, duration: Double) {
    guard left >= 0, right >= 0, left <= maxDriveSpeed, right <= maxDriveSpeed else {
        exitWithUsage("drive speed must be between 0 and \(maxDriveSpeed)")
    }

    guard duration >= minDriveDuration && duration <= maxDriveDuration else {
        exitWithUsage("drive duration must be between \(formatSeconds(minDriveDuration)) and \(formatSeconds(maxDriveDuration)) seconds")
    }
}

private func printUsage() {
    print("""
    Usage:
      swift tools/altino_ble_write.swift scan [--seconds 8]
      swift tools/altino_ble_write.swift light on|off
      swift tools/altino_ble_write.swift horn on|off
      swift tools/altino_ble_write.swift drive <left-speed> <right-speed> <seconds>
      swift tools/altino_ble_write.swift stop

    Drive safety:
      left-speed and right-speed are wheel speeds in the range 0...\(maxDriveSpeed)
      seconds must be \(formatSeconds(minDriveDuration))...\(formatSeconds(maxDriveDuration))
      drive always sends \(stopBurstCount) automatic stop packets after the requested duration
      reverse/negative speeds are disabled until they are verified on the physical Altino
      light and horn commands send complete safe frames with motors stopped

    Examples:
      swift tools/altino_ble_write.swift scan
      swift tools/altino_ble_write.swift light on
      swift tools/altino_ble_write.swift horn off
      swift tools/altino_ble_write.swift drive 200 200 1.0
      swift tools/altino_ble_write.swift drive 100 200 0.5
      swift tools/altino_ble_write.swift stop
    """)
}

private func exitWithUsage(_ message: String) -> Never {
    fputs("error: \(message)\n\n", stderr)
    printUsage()
    exit(64)
}

private func exitWithError(_ message: String, code: Int32) -> Never {
    fputs("error: \(message)\n", stderr)
    exit(code)
}

private func androidPacket(steering: UInt8 = 0, right: Int = 0, left: Int = 0, sound: UInt8 = 0, light: UInt8 = 0) -> Data {
    var tx = [UInt8](repeating: 0, count: 22)
    tx[0] = 0x02
    tx[1] = 0x10
    tx[3] = 0x01
    tx[4] = 0x01
    tx[5] = steering
    putMotor(right, into: &tx, high: 6, low: 7)
    putMotor(left, into: &tx, high: 8, low: 9)
    tx[19] = sound
    tx[20] = light
    tx[21] = 0x03
    tx[2] = UInt8(tx[3..<21].reduce(0) { Int($0) + Int($1) } % 256)
    return Data(tx)
}

private func putMotor(_ value: Int, into tx: inout [UInt8], high: Int, low: Int) {
    let limited = max(-1000, min(1000, value))
    let encoded = limited < 0 ? ((-limited) ^ 0xffff) : limited
    tx[high] = UInt8((encoded >> 8) & 0xff)
    tx[low] = UInt8(encoded & 0xff)
}

private func peripheralName(_ peripheral: CBPeripheral, advertisementData: [String : Any]) -> String {
    peripheral.name
        ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String
        ?? "<unnamed>"
}

private func hex(_ data: Data) -> String {
    data.map { String(format: "%02x", $0) }.joined(separator: " ")
}

private func formatSeconds(_ value: Double) -> String {
    String(format: "%.2f", value)
}

private func stateName(_ state: CBManagerState) -> String {
    switch state {
    case .unknown:
        return "unknown"
    case .resetting:
        return "resetting"
    case .unsupported:
        return "unsupported"
    case .unauthorized:
        return "unauthorized"
    case .poweredOff:
        return "poweredOff"
    case .poweredOn:
        return "poweredOn"
    @unknown default:
        return "future"
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

private let command = parseCommand()
print("altino-cli \(command)")

switch command {
case .scan(let seconds):
    let scanner = Scanner(seconds: seconds)
    DispatchQueue.main.asyncAfter(deadline: .now() + seconds) {
        scanner.stopAndExit()
    }
    RunLoop.main.run()

case .device(let deviceCommand):
    let runner = CommandRunner(command: deviceCommand)

    signal(SIGINT, SIG_IGN)
    signal(SIGTERM, SIG_IGN)

    let sigint = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
    sigint.setEventHandler {
        runner.interruptStopAndExit(signalName: "SIGINT")
    }
    sigint.resume()

    let sigterm = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
    sigterm.setEventHandler {
        runner.interruptStopAndExit(signalName: "SIGTERM")
    }
    sigterm.resume()

    DispatchQueue.main.asyncAfter(deadline: .now() + deviceCommand.timeoutSeconds) {
        runner.timeoutStopAndExit()
    }

    RunLoop.main.run()
}

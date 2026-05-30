# Altino ROS2 Lab

Separate mobile-robot portfolio project for Altino Lite.

This project is intentionally split from MotionBrain:

- MotionBrain: manipulator, STM32 firmware, actuator control, embedded evidence.
- Altino ROS2 Lab: mobile robot, BLE driver, ROS2 command bridge, safety, optional SLAM/Nav.

## Current Status

- macOS Swift BLE CLI can control Altino Lite through the verified Android-style BLE protocol.
- Python protocol code now reproduces the verified 22-byte frames and 14+8 BLE chunk split.
- Python BLE transport is verified on Raspberry Pi/Linux through `bleak`.
- ROS2 `/cmd_vel` to BLE bridge is verified on Raspberry Pi with watchdog stop.

Start from `.codex/START_HERE.md` in a new Codex session. `.codex/` is local working memory and is intentionally ignored by git.

## Verified BLE Protocol

- Device name hint: `ALTINO`
- Service UUID: `49535343-FE7D-4AE5-8FA9-9FAFD205E455`
- Notify/read characteristic: `49535343-1E4D-4BD9-BA61-23C647249616`
- Write characteristic: `49535343-8841-43F4-A8D4-ECBE34729BB3`
- Frame length: 22 bytes
- Frame byte 1: `0x10`
- Write mode: write without response
- Android-style split: first 14 bytes, then remaining 8 bytes

## macOS Reference CLI

```sh
swift tools/altino_ble_write.swift scan
swift tools/altino_ble_write.swift light on
swift tools/altino_ble_write.swift light off
swift tools/altino_ble_write.swift horn on
swift tools/altino_ble_write.swift horn off
swift tools/altino_ble_write.swift drive 200 200 1.0
swift tools/altino_ble_write.swift stop
```

The Swift CLI keeps movement conservative: forward-only wheel speeds `0...350`, drive duration `0.05...3.00` seconds, and automatic stop burst after every drive command.

## Python/Pi CLI

Dry-run frame verification works without BLE hardware:

```sh
python3 -m altino.cli --dry-run light on
python3 -m altino.cli --dry-run drive 200 200 1.0
python3 -m altino.cli --dry-run stop
```

On Raspberry Pi/Linux, install BLE support:

```sh
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements-pi.txt
```

The `--system-site-packages` flag matters for ROS2: it lets the venv see
ROS2's apt-installed Python dependencies while keeping `bleak` isolated.

Then run:

```sh
python3 -m altino.cli scan
python3 -m altino.cli light on
python3 -m altino.cli horn on
python3 -m altino.cli drive 200 200 1.0
python3 -m altino.cli stop
```

Pi hardware verification on 2026-05-30:

- discovered `ALTINO-L11B2` at `E8:31:CD:B4:0E:E2`
- light on/off worked
- horn worked
- `drive 350 350 2.0` produced visible forward movement
- lower direct-drive tests at `120` and `250` were not visually obvious

## Tests

```sh
python3 -m unittest discover -s tests
```

The tests cover known stop/light frames, checksum behavior, Android chunking, motor byte order, `/cmd_vel` mapping, and current forward-only safety limits.

## ROS2 Bridge Foundation

The ROS2 node is optional at import time, so non-ROS tests still run on macOS:

```sh
python3 -m altino.ros2_driver
```

On a Raspberry Pi with ROS2 sourced and BLE support installed, run:

```sh
python3 -m altino.ros2_driver --ros-args --params-file config/altino_driver.yaml
```

or with the standalone launch file:

```sh
ros2 launch ./launch/altino_driver.launch.py
```

Node behavior:

- subscribes to `/cmd_vel`
- publishes text status on `/driver_state`
- converts forward `/cmd_vel` commands into left/right wheel speeds
- rejects reverse and pivot commands until negative wheel behavior is physically verified
- sends stop on zero command and stale command watchdog timeout

Verified ROS2 result on Raspberry Pi:

- `/cmd_vel` subscription appeared
- `/driver_state` published `drive left=350 right=350 reason=drive`
- stale command watchdog published `stop reason=watchdog_timeout`
- direct driver shutdown left no `altino`/`ros2`/daemon processes behind
- a ROS2 speed sweep mapped `linear.x` values `0.15`, `0.20`, `0.25`, `0.30`, and `0.35` to wheel speeds `150`, `200`, `250`, `300`, and `350`, with watchdog stop after each command

The default `wheel_base_m` and `max_linear_mps` values are placeholders for safe bring-up. Calibrate them on the physical Altino before using the values as odometry or navigation evidence.

Pi hardware steps are in `docs/pi_bringup_checklist.md`. Do not run them while another session is using the same Pi for MotionBrain.

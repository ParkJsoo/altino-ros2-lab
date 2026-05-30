# Altino Portfolio Plan

## Phase 1: Driver Foundation - Done

- Move current Swift BLE proof tools into this project.
- Create a clean CLI with:
  - scan
  - light on/off
  - horn on/off
  - drive left/right duration
  - stop
- Add command clamps and automatic stop.

## Phase 2: Raspberry Pi Port - Done

- Implement a Linux/Pi driver using Python `bleak` or BlueZ.
- Verify the same Android-style 22-byte split-frame protocol.
- Keep macOS Swift scripts as reference tools.

Current implementation:

- `altino/protocol.py` builds verified 22-byte frames and Android 14+8 BLE chunks.
- `altino/ble_client.py` provides an async `bleak` transport for Raspberry Pi/Linux.
- `altino/cli.py` provides dry-run frame inspection and hardware commands.
- `tests/test_protocol.py` verifies known packet captures and safety constraints.

Verified on Raspberry Pi:

- BlueZ installed and controller active.
- BLE scan found `ALTINO-L11B2` at `E8:31:CD:B4:0E:E2`.
- Light, horn, stop, and visible forward movement worked.
- Visible movement required `350 350` for the initial floor test; lower values need calibration.

## Phase 3: ROS2 Bridge - In Progress

- Create `altino_driver`.
- Subscribe to `/cmd_vel`.
- Publish `/driver_state`.
- Add watchdog stop on timeout.
- Add launch file and basic tests.

Current implementation:

- `altino/cmd_vel.py` converts planar `/cmd_vel` values into conservative forward-only wheel commands.
- `altino/driver_core.py` keeps command handling and watchdog behavior testable without ROS2 or BLE hardware.
- `altino/ros2_driver.py` defines an optional ROS2 node entry point.
- The node subscribes to `/cmd_vel`, publishes `/driver_state`, and uses a stale-command watchdog.
- `tests/test_cmd_vel.py` and `tests/test_driver_core.py` verify mapping, fake-transport command flow, watchdog stop, reverse rejection, and non-finite input rejection.
- `config/altino_driver.yaml` and `launch/altino_driver.launch.py` prepare Pi-side ROS2 bring-up.
- `docs/pi_bringup_checklist.md` lists the hardware sequence to run only when the Pi is free.

Verified on Raspberry Pi:

- `python3 -m altino.ros2_driver` created `/cmd_vel` and `/driver_state`.
- `/cmd_vel` publish at `linear.x=0.35` produced `drive left=350 right=350`.
- Watchdog published `stop reason=watchdog_timeout`.

Recommended next step:

- Power the Pi back on and verify the patched clean Ctrl-C shutdown path.
- Re-test through `ros2 launch ./launch/altino_driver.launch.py`.
- Tune `wheel_base_m`, `max_linear_mps`, and low-speed threshold before odometry work.

## Phase 4: Sensors

- Add MPU-6050 as `/imu` if useful.
- Add HC-SR04 as `/range/front` and emergency-stop input.
- Keep wiring simple and documented.

## Phase 5: SLAM/Nav Option

- Add 2D LiDAR if budget allows.
- Publish `/scan`.
- Add `base_link`, `laser_link`, and TF.
- Run `slam_toolbox` and save a small indoor map.
- Add simple waypoint or Nav2-style mission demo.

## Evidence To Capture

- Short demo videos.
- ROS graph screenshot.
- RViz screenshot.
- logs/rosbags.
- README diagrams.
- Failure/safety behavior: BLE disconnect, stale `/cmd_vel`, obstacle stop.

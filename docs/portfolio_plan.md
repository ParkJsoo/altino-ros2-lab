# Altino Portfolio Plan

## Phase 1: Driver Foundation

- Move current Swift BLE proof tools into this project.
- Create a clean CLI with:
  - scan
  - light on/off
  - horn on/off
  - drive left/right duration
  - stop
- Add command clamps and automatic stop.

## Phase 2: Raspberry Pi Port

- Implement a Linux/Pi driver using Python `bleak` or BlueZ.
- Verify the same Android-style 22-byte split-frame protocol.
- Keep macOS Swift scripts as reference tools.

## Phase 3: ROS2 Bridge

- Create `altino_driver`.
- Subscribe to `/cmd_vel`.
- Publish `/driver_state`.
- Add watchdog stop on timeout.
- Add launch file and basic tests.

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


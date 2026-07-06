# Altino Portfolio Plan

## Phase 1: Driver Foundation - Done

- Move current Swift BLE proof tools into this project.
- Create a clean CLI with:
  - scan
  - light on/off
  - horn on/off
  - drive motor values and duration
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

## Phase 3: ROS2 Bridge + Open-Loop Odom/TF - Done

- Create `altino_driver`.
- Subscribe to `/cmd_vel`.
- Publish `/driver_state`.
- Add watchdog stop on timeout.
- Publish open-loop `/odom` from accepted drive commands.
- Broadcast `odom -> base_footprint` TF.
- Document drift and reset-on-start behavior.
- Add launch file and basic tests.

Current implementation:

- `altino/cmd_vel.py` converts straight forward `/cmd_vel` values into conservative equal motor commands and maps angular commands to verified Android left/right steering frames.
- `altino/driver_core.py` keeps command handling and watchdog behavior testable without ROS2 or BLE hardware.
- `altino/ros2_driver.py` defines an optional ROS2 node entry point.
- The node subscribes to `/cmd_vel`, publishes `/driver_state` and command-derived `/odom`, broadcasts `odom -> base_footprint`, and uses a stale-command watchdog.
- `description/altino_lite.urdf.xacro` and `launch/altino_bringup.launch.py` add `robot_state_publisher` for `base_footprint -> base_link`.
- `/emergency_stop` and `/clear_emergency_stop` provide a latched stop path before sensor-backed stops exist.
- `altino/odom_model.py` integrates accepted commands as explicit open-loop odometry without ROS2, BLE, or hardware dependencies.
- `altino/calibration.py` summarizes manual straight/yaw trials into candidate config values.
- `tests/test_cmd_vel.py` and `tests/test_driver_core.py` verify mapping, fake-transport command flow, watchdog stop, reverse rejection, angular steering, and non-finite input rejection.
- `tests/test_odom_model.py` verifies straight integration, stop/rejected-command handling, steering yaw defaults, optional yaw-rate integration, covariance shape, and timestamp sanity.
- `config/altino_driver.yaml` and `launch/altino_driver.launch.py` prepare Pi-side ROS2 bring-up.
- `docs/pi_bringup_checklist.md` lists the hardware sequence to run only when the Pi is free.

Verified on Raspberry Pi:

- `python3 -m altino.ros2_driver` created `/cmd_vel` and `/driver_state`.
- `/cmd_vel` publish at `linear.x=0.35` produced `drive left=350 right=350`.
- Watchdog published `stop reason=watchdog_timeout`.
- Android-captured steering frames were physically verified from the Pi driver: left/right steering, center return, and left/right drive steering worked.
- Speed calibration found `linear.x=0.26` borderline and `linear.x=0.30` stable for forward motion.
- ROS2 angular commands at `linear.x=0.30` produced clear left and right steering with similar turn ratio.

Recommended next step:

- Keep `linear.x=0.30` as the stable bring-up speed and avoid claiming calibrated curvature until manual calibration or sensor-backed odometry exists.
- Treat pre-sensor odom as an integration scaffold, not a localization source.
- Capture bringup RViz with the robot model and run manual calibration trials before sensor work.

## Phase 4: Pre-Sensor Evidence - In Progress

- Capture ROS graph evidence with `/cmd_vel`, `/driver_state`, `/odom`, and `/tf`.
- Capture `tf2_echo odom base_footprint` and verify `base_footprint -> base_link` from `robot_state_publisher`.
- Capture RViz with fixed frame `odom`, TF, and Odometry displays.
- Capture e-stop latch and clear-service evidence.
- Record rosbag/logs for straight, left steering, right steering, zero stop, and watchdog stop.
- Document that open-loop odom resets on node start and drifts from physical motion.
- Use `tools/raspi/motionbrain-off-for-altino.sh` before capture so the shared Pi is cleanly in Altino mode.
- Use `tools/raspi/altino-preflight.sh` to verify MotionBrain is inactive and required ROS2 packages are present.
- Run `docs/manual_calibration.md` and record measured config candidates.

Current evidence:

- `docs/evidence/2026-07-06-rviz-clean/`: original `/odom` and RViz path before `base_footprint` split.
- `docs/evidence/2026-07-06-bringup-estop/`: current `odom -> base_footprint -> base_link`, RobotModel, and e-stop latch evidence.

## Phase 5: Sensors

- Add MPU-6050 as `/imu` if useful.
- Add HC-SR04 as `/range/front` and emergency-stop input.
- Keep wiring simple and documented.

## Phase 6: LiDAR / Mapping Option

- Add 2D LiDAR if budget allows.
- Publish `/scan`.
- Add `laser_link` or `base_scan` TF after the LiDAR mount exists.
- Run `slam_toolbox` and save a small indoor map.
- Add simple waypoint or Nav2-style mission demo.

## Evidence To Capture

- Short demo videos.
- ROS graph screenshot.
- RViz screenshot.
- `tf2_echo odom base_link` output.
- logs/rosbags.
- README diagrams.
- Failure/safety behavior: BLE disconnect, stale `/cmd_vel`, obstacle stop.

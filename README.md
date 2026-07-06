# Altino ROS2 Lab

[한국어 README](README.ko.md)

Altino ROS2 Lab is a mobile-robot portfolio project for Altino Lite. It builds a
verified BLE driver, a ROS2 `/cmd_vel` bridge, watchdog and e-stop safety paths,
open-loop odom/TF, and a pre-sensor RViz bringup stack.

This project is intentionally separate from MotionBrain:

- MotionBrain: manipulator, STM32 firmware, actuator control, embedded evidence.
- Altino ROS2 Lab: mobile base, BLE transport, ROS2 integration, TF/RViz evidence.

## Current Status

- BLE CLI and Pi `bleak` transport are verified with the Android-style 22-byte, 14+8 split-write protocol.
- ROS2 `/cmd_vel` control is verified on Raspberry Pi with `/driver_state` and watchdog stop.
- Left/right steering uses verified Android BLE packets.
- The driver publishes command-integrated `/odom` and `odom -> base_footprint` TF.
- Bringup provides `base_footprint -> base_link` through `robot_state_publisher`.
- RViz evidence exists for odom/TF, RobotModel, e-stop latch, and clear service.

## System Shape

```text
/cmd_vel
  -> altino_driver
       -> BLE write -> Altino Lite
       -> /driver_state
       -> /odom
       -> /tf: odom -> base_footprint

robot_state_publisher
  -> /tf_static: base_footprint -> base_link

/emergency_stop
  -> latched stop
/clear_emergency_stop
  -> clear latch
```

## Safety and Limits

- Stop MotionBrain before Altino hardware tests on the shared Raspberry Pi.
- Keep clear floor space; movement commands are real BLE writes to the robot.
- Watchdog stop, zero-command stop, and latched e-stop are implemented.
- Reverse commands are rejected until reverse behavior is physically verified.
- Angular `/cmd_vel` selects discrete verified steering states, not calibrated curvature.
- `/odom` is command-integrated only. It is not encoder, IMU, LiDAR, SLAM, localization, Nav2, or obstacle-avoidance evidence.

## Run Tests

```sh
python3 -m unittest discover -s tests
```

The tests cover protocol frames, Android chunking, `/cmd_vel` mapping, driver
state flow, watchdog stop, e-stop latch, open-loop odom, calibration helpers,
and robot-description consistency.

## BLE CLI

Dry-run without hardware:

```sh
python3 -m altino.cli --dry-run light on
python3 -m altino.cli --dry-run drive 200 200 1.0
python3 -m altino.cli --dry-run stop
```

On Raspberry Pi:

```sh
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements-pi.txt

python3 -m altino.cli scan
python3 -m altino.cli light on
python3 -m altino.cli drive 200 200 1.0
python3 -m altino.cli steer left 300 1.0
python3 -m altino.cli stop
```

Use `--system-site-packages` so the venv can see ROS2 Python packages while
keeping Pi-only Python dependencies isolated.

## ROS2 Bringup

Source ROS2 and activate the Pi venv:

```sh
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=42
```

Driver only:

```sh
python3 -m altino.ros2_driver --ros-args --params-file config/altino_driver.yaml
```

Full pre-sensor bringup with robot model and optional RViz:

```sh
ros2 launch ./launch/altino_bringup.launch.py rviz:=true
```

Safety check:

```sh
ros2 topic pub --once /emergency_stop std_msgs/msg/Bool "{data: true}"
ros2 service call /clear_emergency_stop std_srvs/srv/Trigger "{}"
```

## Raspberry Pi Mode Switching

The current setup shares one Raspberry Pi with MotionBrain. Stop MotionBrain
before Altino hardware tests:

```sh
tools/raspi/motionbrain-off-for-altino.sh
tools/raspi/altino-preflight.sh
```

Restore MotionBrain afterward:

```sh
tools/raspi/motionbrain-on.sh
```

## Evidence

- `docs/evidence/2026-07-06-rviz-clean/`: original RViz odom/TF capture before the `base_footprint` split.
- `docs/evidence/2026-07-06-bringup-estop/`: current `odom -> base_footprint -> base_link`, RobotModel, e-stop latch, and clear-service capture.
- `docs/pi_bringup_checklist.md`: Pi bringup and hardware verification checklist.
- `docs/manual_calibration.md`: manual distance/yaw calibration workflow before adding sensors.
- `docs/calibration_trials_template.csv`: CSV template for manual calibration trials.
- `docs/portfolio_plan.md`: roadmap from BLE driver to sensors, LiDAR, SLAM, and Nav2.

## Next Work

Before sensors: collect manual calibration data for straight speed and steering
yaw rate.

After sensors: add measured `/imu`, `/range` or `/scan`, then revisit
localization, SLAM, Nav2, and obstacle avoidance claims with sensor-backed
evidence.

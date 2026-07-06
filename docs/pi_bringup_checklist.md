# Raspberry Pi Bring-Up Checklist

Use this only when the Raspberry Pi is not being used by MotionBrain.

Before Altino hardware tests from the Mac, stop MotionBrain's auto-reconcile
timer and services:

```sh
tools/raspi/motionbrain-off-for-altino.sh
```

This prompts for the Pi sudo password if needed and verifies these units are
inactive:

- `motionbrain-dashboard-reconcile.timer`
- `motionbrain-dashboard-reconcile.service`
- `motionbrain-dashboard.service`
- `motionbrain-perception.service`
- `motionbrain-ros-bridge.service`

After Altino testing, restore MotionBrain:

```sh
tools/raspi/motionbrain-on.sh
```

## 1. Prepare an isolated Python environment

```sh
cd ~/altino-ros2-lab
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements-pi.txt
```

Use `--system-site-packages` so the venv can see ROS2's apt-installed
Python dependencies while still adding Pi-only packages such as `bleak`.

## 2. Check BLE discovery

```sh
python3 -m altino.cli scan
```

Expected:

- a device with name containing `ALTINO`
- RSSI shown
- no system Bluetooth service restart required

If scan fails, stop here. Do not change BlueZ or system services while another project is using the Pi.

## 3. Verify safe direct commands

Keep the Altino lifted or with clear floor space.

```sh
python3 -m altino.cli light on
python3 -m altino.cli light off
python3 -m altino.cli horn on
python3 -m altino.cli horn off
python3 -m altino.cli drive 120 120 0.5
python3 -m altino.cli stop
```

Expected:

- light and horn respond
- short forward motion works
- drive stops automatically
- explicit stop also succeeds

Observed on 2026-05-30: light and horn worked; movement became clearly visible
with `drive 350 350 2.0` on open floor. Tests at `120` and `250` were not
visually obvious.

## 4. Run the ROS2 driver

Source ROS2 first, then keep the same venv active.

```sh
source /opt/ros/$ROS_DISTRO/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=42
python3 -m altino.ros2_driver --ros-args --params-file config/altino_driver.yaml
```

On the current Pi, ROS2 is Jazzy. If `ROS_DISTRO` is empty, use:

```sh
source /opt/ros/jazzy/setup.bash
```

Alternative with the standalone launch file:

```sh
ros2 launch ./launch/altino_driver.launch.py
```

Run the launch command from the same activated venv so `python3` can import
`bleak`.

Full pre-sensor bringup with robot model and optional RViz:

```sh
ros2 launch ./launch/altino_bringup.launch.py rviz:=true
```

This requires ROS2 packages `robot_state_publisher`, `xacro`, and `rviz2`.
The TF chain is `odom -> base_footprint -> base_link`. Planned IMU/range/LiDAR
placeholder frames are off by default; enable them only for mount planning:

```sh
ros2 launch ./launch/altino_bringup.launch.py include_sensor_placeholders:=true
```

## 5. Test `/cmd_vel`

In a second terminal with the same ROS2 environment:

```sh
export ROS_DOMAIN_ID=42
ros2 topic echo /driver_state
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.35}, angular: {z: 0.0}}"
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.30}, angular: {z: 0.5}}"
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.30}, angular: {z: -0.5}}"
```

Expected:

- `/driver_state` reports a drive command
- the robot moves slowly forward
- positive `angular.z` steers left with equal motor speed
- negative `angular.z` steers right with equal motor speed
- after the command becomes stale, `/driver_state` reports `watchdog_timeout`
- Altino stops

Safety checks:

```sh
ros2 topic pub --once /emergency_stop std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.30}, angular: {z: 0.0}}"
ros2 service call /clear_emergency_stop std_srvs/srv/Trigger "{}"
```

Expected:

- `/emergency_stop` immediately sends a stop and latches the driver.
- `/cmd_vel` while latched reports `stop reason=emergency_stop_active`.
- false `/emergency_stop` messages do not clear the latch.
- `/clear_emergency_stop` clears the latch.

Observed on 2026-05-30:

- `/cmd_vel` had one subscriber
- `/driver_state` reported `drive left=350 right=350 reason=drive`
- watchdog then reported `stop reason=watchdog_timeout`
- direct driver shutdown left no `altino`/`ros2`/daemon processes behind

ROS2 speed sweep observed on 2026-05-30 with `cmd_timeout_s:=1.0`:

```text
linear.x=0.15 -> drive left=150 right=150 -> stop reason=watchdog_timeout
linear.x=0.20 -> drive left=200 right=200 -> stop reason=watchdog_timeout
linear.x=0.25 -> drive left=250 right=250 -> stop reason=watchdog_timeout
linear.x=0.30 -> drive left=300 right=300 -> stop reason=watchdog_timeout
linear.x=0.35 -> drive left=350 right=350 -> stop reason=watchdog_timeout
```

This confirms the ROS2-to-driver mapping and watchdog behavior.

Low-speed repeat tests on 2026-05-31:

```text
linear.x=0.18 -> drive left=180 right=180 -> no reliable visible movement
linear.x=0.22 -> drive left=220 right=220 -> no reliable visible movement
linear.x=0.26 -> drive left=260 right=260 -> moved in 2 of 3 repeat trials
linear.x=0.30 -> drive left=300 right=300 -> moved in 3 of 3 repeat trials
```

Use `linear.x=0.30` as the first stable forward motion threshold for bring-up.
Treat `linear.x=0.26` as a borderline diagnostic value, not a reliable default.

Follow-up direct motor differential tests on 2026-05-30:

```text
left=0 right=350 -> physically observed as straight
left=350 right=0 -> physically observed as straight
```

Follow-up steering-byte tests on 2026-05-30:

```text
steering=1,2,3 with equal motor speeds -> physically observed as straight
steering=127 and steering=255 -> visible steering hunting, not reliable turning
```

Conclusion: the differential-drive interpretation is invalid for this Altino BLE
path. Use the Android app's actual left/right steering BLE packets instead.

Android Orchestra steering capture on 2026-05-31 decoded these frames:

```text
left turn:  byte5=0x80, equal motor fields, byte20=0x04
right turn: byte5=0x7f, equal motor fields, byte20=0x08
```

Physical verification on 2026-05-31 from the Pi driver:

- `CAPTURED_LEFT_STEER_ONLY` moved the front wheels left.
- center/stop frames returned the wheels to center.
- `CAPTURED_LEFT_DRIVE` and `CAPTURED_RIGHT_DRIVE` produced left/right steering while driving.
- `CAPTURED_RIGHT_STEER_ONLY` moved the front wheels right and center/stop returned them.

These are available through `python3 -m altino.cli steer left|right|center`.
ROS2 angular `/cmd_vel` now maps to these discrete steering states: positive is
left, negative is right. Angular magnitude is not calibrated as curvature yet.

ROS2 steering verification on 2026-05-31 with `linear.x=0.30`:

```text
angular.z=+0.50 -> steer direction=left speed=300 -> physically clear left turn
angular.z=-0.50 -> steer direction=right speed=300 -> physically clear right turn
```

Operator observation: left and right turns were similar enough that the robot
returned close to its starting pose after the left/right pair.

## 6. Verify open-loop `/odom` and TF

In a second terminal with the same ROS2 environment:

```sh
export ROS_DOMAIN_ID=42
ros2 topic echo /odom
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo odom base_footprint
```

Expected:

- `/odom` is published while the driver is running.
- `tf2_echo` shows a connected `odom -> base_footprint` transform.
- with bringup active, `robot_state_publisher` provides `base_footprint -> base_link`.
- Pose changes when accepted `/cmd_vel` commands are sent.
- Pose stops changing after zero command, rejected command, or watchdog stop.
- The observed path is command-integrated and may drift from physical motion.

RViz check:

- Use `config/altino_odom_tf.rviz`, or manually set fixed frame to `odom`.
- Add TF display.
- Add Odometry display for `/odom`.
- Capture a screenshot before adding sensors or LiDAR.

Captured on 2026-07-06 in `docs/evidence/2026-07-06-rviz-clean/`:

- MotionBrain services and the reconcile timer stayed inactive during capture.
- `/cmd_vel` had one subscriber: `altino_driver`.
- five `linear.x=0.30` commands produced `/driver_state` drive messages followed by `stop reason=watchdog_timeout`.
- `/odom` and `odom -> base_link` TF matched at `x=0.2754192056999273`.
- RViz displayed Grid, TF, and `/odom` without captured warnings or errors.

That capture predates the `base_footprint` split. Current bringup should use
`odom -> base_footprint -> base_link`.

Captured on 2026-07-06 in `docs/evidence/2026-07-06-bringup-estop/`:

- `altino_bringup.launch.py` started `robot_state_publisher`, `altino_driver`,
  and RViz.
- RViz displayed Grid, TF, RobotModel, and `/odom`.
- `/odom` used `child_frame_id: base_footprint`.
- `tf2_echo` confirmed `odom -> base_footprint` and `base_footprint -> base_link`.
- `/emergency_stop` latched the driver and blocked later `/cmd_vel` as
  `stop reason=emergency_stop_active`.
- `/clear_emergency_stop` returned `success=True`.

## Stop Conditions

Stop and investigate if any of these happen:

- command runs but no automatic stop occurs
- reverse command causes movement
- pure pivot command causes translation instead of stationary steering
- BLE disconnect does not stop the robot
- MotionBrain services or hardware access are active on the same Pi

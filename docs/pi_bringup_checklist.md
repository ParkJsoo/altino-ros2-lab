# Raspberry Pi Bring-Up Checklist

Use this only when the Raspberry Pi is not being used by MotionBrain.

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

## 5. Test `/cmd_vel`

In a second terminal with the same ROS2 environment:

```sh
export ROS_DOMAIN_ID=42
ros2 topic echo /driver_state
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.35}, angular: {z: 0.0}}"
```

Expected:

- `/driver_state` reports a drive command
- the robot moves slowly forward
- after the command becomes stale, `/driver_state` reports `watchdog_timeout`
- Altino stops

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

This confirms the ROS2-to-driver mapping and watchdog behavior. Operator
observation from the same run: visible physical movement was observed at
`linear.x=0.30` and `linear.x=0.35`; movement below `0.30` is not yet confirmed
as a reliable physical threshold.

ROS2 arc sweep observed on 2026-05-30 with `linear.x=0.30`,
`cmd_timeout_s:=1.0`, and `wheel_base_m=0.12`:

```text
angular.z=+0.50 -> drive left=270 right=330 -> stop reason=watchdog_timeout
angular.z=-0.50 -> drive left=330 right=270 -> stop reason=watchdog_timeout
```

This confirms differential wheel mapping for forward arc commands. Record
operator observation separately before treating the sign of `angular.z` as
physically verified for left/right turns.

## Stop Conditions

Stop and investigate if any of these happen:

- command runs but no automatic stop occurs
- reverse or pivot command causes movement
- BLE disconnect does not stop the robot
- MotionBrain services or hardware access are active on the same Pi

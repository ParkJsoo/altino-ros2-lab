# Altino Bringup RobotModel/E-Stop Capture - 2026-07-06

## Result

Captured the current pre-sensor bringup path with the updated TF split:

```text
odom -> base_footprint -> base_link
```

The capture ran `altino_bringup.launch.py` with `robot_state_publisher`,
`altino_driver`, and RViz. MotionBrain services and the reconcile timer stayed
inactive during capture and were restored afterward.

## MotionBrain State

Before capture:

```text
motionbrain-dashboard-reconcile.timer active=inactive
motionbrain-dashboard-reconcile.service active=inactive
motionbrain-dashboard.service active=inactive
motionbrain-perception.service active=inactive
motionbrain-ros-bridge.service active=inactive
```

After capture:

```text
motionbrain-dashboard-reconcile.timer active=inactive
motionbrain-dashboard-reconcile.service active=inactive
motionbrain-dashboard.service active=inactive
motionbrain-perception.service active=inactive
motionbrain-ros-bridge.service active=inactive
```

## Captured Evidence

- `altino_bringup_estop_rviz.png`: RViz screenshot with Grid, TF, RobotModel, and `/odom`.
- `topics_before_estop.txt`: `/cmd_vel`, `/driver_state`, `/emergency_stop`, `/joint_states`, `/odom`, `/robot_description`, `/tf`, and `/tf_static` were present.
- `services_before_estop.txt`: `/clear_emergency_stop` was present.
- `cmd_vel_info_before_estop.txt`: `/cmd_vel` had one subscription, the `altino_driver` node.
- `driver_state_stream.txt`: e-stop emitted `stop reason=emergency_stop`; later `/cmd_vel` messages were blocked as `stop reason=emergency_stop_active`.
- `clear_emergency_stop_call.log`: `/clear_emergency_stop` returned `success=True` with `emergency_stop_cleared`.
- `odom_after_estop.txt`: `/odom` used `child_frame_id: base_footprint`.
- `tf2_echo_odom_base_footprint.txt`: dynamic `odom -> base_footprint` transform was available.
- `tf2_echo_base_footprint_base_link.txt`: static `base_footprint -> base_link` transform was available with `z=0.030`.
- `altino_lite.expanded.urdf`: expanded xacro model used by bringup.

## Scope

This validates pre-sensor robot model bringup, TF frame split, RViz RobotModel
display, and latched e-stop control. It does not validate measured odometry,
localization, SLAM, Nav2, obstacle avoidance, or calibrated motion.

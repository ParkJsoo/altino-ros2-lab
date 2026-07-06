# Altino Clean RViz Odom/TF Capture - 2026-07-06

## Result

Captured a clean RViz visualization of the pre-sensor ROS2 path while
MotionBrain services and the reconcile timer stayed inactive:

```text
/cmd_vel -> altino_driver -> /driver_state -> /odom -> /tf -> RViz
```

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

MotionBrain was restored after the capture.

## Captured Evidence

- `altino_rviz_clean.png`: RViz screenshot with fixed frame `odom`, TF, and `/odom` display.
- `cmd_vel_info_before_pub.txt`: `/cmd_vel` had one subscription, the `altino_driver` node.
- `cmd_vel_pub.log`: published five `linear.x=0.30` `/cmd_vel` messages.
- `driver_state_stream.txt`: driver emitted five `drive left=300 right=300 reason=drive` states, then `stop reason=watchdog_timeout`.
- `topics_before_cmd.txt`: `/cmd_vel`, `/driver_state`, `/odom`, and `/tf` were present.
- `odom_after_cmd.txt`: final `/odom` pose had `x=0.2754192056999273` and zero twist after watchdog stop.
- `tf_after_cmd.txt`: final `odom -> base_link` TF had matching `x=0.2754192056999273`.
- `altino_driver.log`: driver connected to Altino over BLE.
- `rviz.log`: RViz started without warnings or errors in the captured log.
- `screenshot_identify.txt`: captured PNG metadata, `1600x1000`.

## Scope

This validates command-integrated open-loop odom/TF plumbing and RViz
visualization only. It is not measured odometry, localization, SLAM, Nav2, or
obstacle avoidance evidence.

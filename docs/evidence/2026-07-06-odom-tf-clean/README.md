# Altino Clean Open-Loop Odom/TF Capture - 2026-07-06

## Result

Captured a clean ROS2 command path while MotionBrain services and the reconcile
timer stayed inactive:

```text
/cmd_vel -> altino_driver -> /driver_state -> /odom -> /tf
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

- `altino_clean_topics.txt`: `/cmd_vel`, `/driver_state`, `/odom`, and `/tf` were present.
- `altino_clean_driver.log`: driver connected to Altino over BLE.
- `altino_clean_cmd_pub.txt`: published one `linear.x=0.30` `/cmd_vel`.
- `altino_clean_driver_state_capture.txt`: driver emitted `drive left=300 right=300 reason=drive`, then `stop reason=watchdog_timeout`.
- `altino_clean_tf_capture.txt`: `tf2_echo odom base_link` observed translation progress to about `0.153` m.
- `altino_clean_odom_after.txt`: final `/odom` pose had `x=0.15341108909979084` and zero twist after watchdog stop.
- `altino_clean_zero_stop.txt`: a zero `/cmd_vel` was sent during driver cleanup.

## Scope

This validates command-integrated open-loop odom/TF plumbing only. It is not
measured odometry, localization, SLAM, Nav2, or obstacle avoidance evidence.

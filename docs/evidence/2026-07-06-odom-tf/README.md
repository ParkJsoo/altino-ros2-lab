# Altino Open-Loop Odom/TF Capture - 2026-07-06

## Result

Captured the ROS2 command path:

```text
/cmd_vel -> altino_driver -> /driver_state -> /odom -> /tf
```

The driver connected to Altino over BLE and published `/odom` plus `odom -> base_link` TF.

## Important Caveat

This capture does **not** satisfy the intended MotionBrain-inactive precondition.

MotionBrain services were stopped once through the interactive cmux SSH session, but they restarted before the capture script ran:

```text
motionbrain-ros-bridge.service active=active
motionbrain-perception.service active=active
motionbrain-dashboard.service active=active
```

Use this evidence only as a functional `/odom` and TF smoke test. Re-run the capture after MotionBrain service restart behavior is controlled.

Superseded by the clean capture in:

```text
docs/evidence/2026-07-06-odom-tf-clean/
```

## Captured Evidence

- `altino_topics.txt`: `/cmd_vel`, `/driver_state`, `/odom`, `/tf` were present.
- `altino_driver.log`: driver BLE connection succeeded.
- `altino_cmd_pub.txt`: published one `linear.x=0.30` `/cmd_vel`.
- `altino_driver_state_capture.txt`: driver emitted `drive left=300 right=300 reason=drive`, then `stop reason=watchdog_timeout`.
- `altino_tf_capture.txt`: `tf2_echo odom base_link` observed translation progress from `0.000` to about `0.165` m.
- `altino_odom_after.txt`: final `/odom` pose had `x=0.16468295100000885` and zero twist after watchdog stop.
- `altino_zero_stop.txt`: a zero `/cmd_vel` was sent before shutting down the driver.

## Scope

This is command-integrated open-loop odometry. It is not measured odometry, localization, SLAM, Nav2, or obstacle avoidance evidence.

# Manual Calibration Before Sensors

Use this only after the ROS2 driver, watchdog, `/odom`, TF, and RViz path are
already working.

## Procedure

1. Put tape on the floor for a straight line and a start pose.
2. Record overhead video if possible, or use a protractor/printed angle guide.
3. Run short trials at the stable bring-up command:

```sh
export ROS_DOMAIN_ID=42
ros2 topic pub -r 10 -t 20 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.30}, angular: {z: 0.0}}"
ros2 topic pub -r 10 -t 20 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.30}, angular: {z: 0.5}}"
ros2 topic pub -r 10 -t 20 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.30}, angular: {z: -0.5}}"
```

4. Measure distance and yaw change, then fill a copy of
   `docs/calibration_trials_template.csv`.
5. Summarize the trials:

```sh
python3 -m altino.calibration docs/calibration_trials_template.csv
```

or, after installing the package:

```sh
altino-calibration docs/calibration_trials_template.csv
```

## Outputs

- `recommended max_linear_mps`: candidate value for `config/altino_driver.yaml`.
- `recommended steering_yaw_rate_radps`: candidate value for open-loop steering
  yaw integration.

Only apply these after at least three repeatable trials per direction. Even
after calibration, this remains open-loop command odometry, not measured
odometry.

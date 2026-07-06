# Altino ROS2 Lab

[English README](README.en.md)

Altino ROS2 Lab은 Altino Lite를 대상으로 한 모바일 로봇 포트폴리오
프로젝트입니다. 검증된 BLE 드라이버, ROS2 `/cmd_vel` 브리지, watchdog/e-stop
안전 경로, open-loop odom/TF, 센서 장착 전 RViz bringup을 다룹니다.

이 프로젝트는 MotionBrain과 역할을 분리합니다.

- MotionBrain: 매니퓰레이터, STM32 펌웨어, 액추에이터 제어, 임베디드 증거.
- Altino ROS2 Lab: 모바일 베이스, BLE 전송, ROS2 통합, TF/RViz 증거.

## 현재 상태

- BLE CLI와 Pi `bleak` 전송을 Android 방식 22바이트, 14+8 split-write 프로토콜로 검증.
- Raspberry Pi에서 ROS2 `/cmd_vel` 제어, `/driver_state`, watchdog stop 검증.
- 좌/우 steering은 검증된 Android BLE 패킷 사용.
- 드라이버는 명령 기반 `/odom`과 `odom -> base_footprint` TF 발행.
- bringup은 `robot_state_publisher`로 `base_footprint -> base_link` 제공.
- odom/TF, RobotModel, e-stop latch, clear service RViz 증거 캡처 완료.

## 시스템 구조

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

## 안전 및 한계

- 공유 Raspberry Pi에서 Altino 하드웨어 테스트 전에는 MotionBrain을 중지합니다.
- 실제 BLE 명령이 로봇에 전달되므로 주변 바닥 공간을 비웁니다.
- watchdog stop, zero-command stop, latched e-stop이 구현되어 있습니다.
- reverse 명령은 실제 동작 검증 전까지 거부합니다.
- angular `/cmd_vel`은 검증된 discrete steering 상태를 선택할 뿐, 보정된 곡률 제어가 아닙니다.
- `/odom`은 명령 적분값입니다. encoder, IMU, LiDAR, SLAM, localization, Nav2, 장애물 회피 증거가 아닙니다.

## 테스트

```sh
python3 -m unittest discover -s tests
```

테스트 범위는 프로토콜 프레임, Android chunking, `/cmd_vel` 매핑, driver 상태
흐름, watchdog stop, e-stop latch, open-loop odom, calibration helper, robot
description 일관성입니다.

## BLE CLI

하드웨어 없이 dry-run:

```sh
python3 -m altino.cli --dry-run light on
python3 -m altino.cli --dry-run drive 200 200 1.0
python3 -m altino.cli --dry-run stop
```

Raspberry Pi에서 실행:

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

`--system-site-packages`는 ROS2 Python 패키지를 venv에서 볼 수 있게 하면서
Pi 전용 Python 의존성은 분리하기 위해 사용합니다.

## ROS2 Bringup

ROS2와 Pi venv를 활성화합니다.

```sh
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
export ROS_DOMAIN_ID=42
```

드라이버만 실행:

```sh
python3 -m altino.ros2_driver --ros-args --params-file config/altino_driver.yaml
```

로봇 모델과 RViz를 포함한 센서 전 bringup:

```sh
ros2 launch ./launch/altino_bringup.launch.py rviz:=true
```

안전 정지 확인:

```sh
ros2 topic pub --once /emergency_stop std_msgs/msg/Bool "{data: true}"
ros2 service call /clear_emergency_stop std_srvs/srv/Trigger "{}"
```

## Raspberry Pi 모드 전환

현재 Raspberry Pi 하나를 MotionBrain과 공유합니다. Altino 하드웨어 테스트 전에는
MotionBrain을 중지합니다.

```sh
tools/raspi/motionbrain-off-for-altino.sh
tools/raspi/altino-preflight.sh
```

테스트 후 MotionBrain을 복구합니다.

```sh
tools/raspi/motionbrain-on.sh
```

## Evidence

- `docs/evidence/2026-07-06-rviz-clean/`: `base_footprint` 분리 전 최초 RViz odom/TF 캡처.
- `docs/evidence/2026-07-06-bringup-estop/`: 현재 `odom -> base_footprint -> base_link`, RobotModel, e-stop latch, clear service 캡처.
- `docs/pi_bringup_checklist.md`: Pi bringup 및 하드웨어 검증 체크리스트.
- `docs/manual_calibration.md`: 센서 추가 전 수동 거리/회전 보정 절차.
- `docs/calibration_trials_template.csv`: 수동 보정 trial 입력용 CSV 템플릿.
- `docs/portfolio_plan.md`: BLE 드라이버에서 센서, LiDAR, SLAM, Nav2로 이어지는 로드맵.

## 다음 작업

센서 전에는 직진 속도와 steering yaw rate 수동 보정 데이터를 수집합니다.

센서 이후에는 `/imu`, `/range` 또는 `/scan` 같은 측정 topic을 추가한 뒤
localization, SLAM, Nav2, 장애물 회피 주장을 센서 기반 증거로 다시 검증합니다.

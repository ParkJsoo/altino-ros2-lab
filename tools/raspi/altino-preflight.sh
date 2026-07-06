#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-motionbrain-pi}"
PROJECT_DIR="${2:-/home/motionbrain/altino-ros2-lab}"

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail

project_dir="$1"
units=(
  motionbrain-dashboard-reconcile.timer
  motionbrain-dashboard-reconcile.service
  motionbrain-dashboard.service
  motionbrain-perception.service
  motionbrain-ros-bridge.service
)

echo "MotionBrain state:"
bad=0
for unit in "${units[@]}"; do
  state="$(systemctl is-active "${unit}" 2>/dev/null || true)"
  printf "%-48s %s\n" "${unit}" "${state}"
  if [[ "${state}" != "inactive" ]]; then
    bad=1
  fi
done

echo
if [[ "${bad}" != "0" ]]; then
  echo "MotionBrain is active. Run tools/raspi/motionbrain-off-for-altino.sh first." >&2
  exit 1
fi

source /opt/ros/jazzy/setup.bash
cd "${project_dir}"
source .venv/bin/activate

echo "ROS2 tools:"
for command in ros2 xacro rviz2; do
  printf "%-16s " "${command}"
  command -v "${command}"
done

echo
echo "ROS2 packages:"
for package in robot_state_publisher rviz2 tf2_ros; do
  printf "%-24s " "${package}"
  ros2 pkg prefix "${package}"
done

echo
echo "Python imports:"
python3 - <<'PY'
import importlib

for name in ("bleak", "rclpy", "nav_msgs", "tf2_ros", "altino.ros2_driver"):
    importlib.import_module(name)
    print(f"{name}: ok")
PY

echo
echo "Altino preflight passed."
REMOTE

ssh "${TARGET}" "bash -lc $(printf "%q" "${REMOTE_SCRIPT}") bash $(printf "%q" "${PROJECT_DIR}")"

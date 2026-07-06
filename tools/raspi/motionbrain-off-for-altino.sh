#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-motionbrain-pi}"

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail

units=(
  motionbrain-dashboard-reconcile.timer
  motionbrain-dashboard-reconcile.service
  motionbrain-dashboard.service
  motionbrain-perception.service
  motionbrain-ros-bridge.service
)

echo "Stopping MotionBrain reconcile timer and services for Altino..."
sudo systemctl stop motionbrain-dashboard-reconcile.timer
sudo systemctl stop motionbrain-dashboard-reconcile.service || true
sudo systemctl stop motionbrain-dashboard.service motionbrain-perception.service motionbrain-ros-bridge.service

echo
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
echo "Relevant processes:"
pgrep -af "motionbrain|altino|ros2|rclpy|bleak" || true

if [[ "${bad}" != "0" ]]; then
  echo "MotionBrain did not fully stop; do not run Altino hardware tests yet." >&2
  exit 1
fi

echo "MotionBrain is inactive. Altino tests may proceed."
REMOTE

ssh -tt "${TARGET}" "bash -lc $(printf "%q" "${REMOTE_SCRIPT}")"

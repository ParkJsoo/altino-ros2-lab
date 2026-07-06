#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-motionbrain-pi}"

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail

units=(
  motionbrain-ros-bridge.service
  motionbrain-perception.service
  motionbrain-dashboard.service
  motionbrain-dashboard-reconcile.timer
)

echo "Starting MotionBrain services..."
sudo systemctl start motionbrain-ros-bridge.service motionbrain-perception.service motionbrain-dashboard.service
sudo systemctl start motionbrain-dashboard-reconcile.timer

echo
echo "MotionBrain state:"
for unit in "${units[@]}"; do
  printf "%-48s " "${unit}"
  systemctl is-active "${unit}" 2>/dev/null || true
done
REMOTE

ssh -tt "${TARGET}" "bash -lc $(printf "%q" "${REMOTE_SCRIPT}")"

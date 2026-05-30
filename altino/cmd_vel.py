"""Conservative ROS2 /cmd_vel conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .protocol import MAX_DRIVE_SPEED, ProtocolError

DEFAULT_WHEEL_BASE_M = 0.12
DEFAULT_MAX_LINEAR_MPS = 0.35
DEFAULT_DEADBAND_MPS = 0.001


@dataclass(frozen=True)
class WheelCommand:
    left: int
    right: int
    should_stop: bool
    accepted: bool
    reason: str


def cmd_vel_to_drive(
    linear_x: float,
    angular_z: float,
    *,
    wheel_base_m: float = DEFAULT_WHEEL_BASE_M,
    max_linear_mps: float = DEFAULT_MAX_LINEAR_MPS,
    max_speed: int = MAX_DRIVE_SPEED,
    deadband_mps: float = DEFAULT_DEADBAND_MPS,
) -> WheelCommand:
    """Convert planar velocity to current safe Altino wheel commands.

    Reverse and pivot commands are intentionally rejected until negative wheel
    encoding is verified on the physical Altino.
    """

    validate_float(linear_x, "linear_x")
    validate_float(angular_z, "angular_z")
    validate_positive_float(wheel_base_m, "wheel_base_m")
    validate_positive_float(max_linear_mps, "max_linear_mps")
    validate_positive_float(deadband_mps, "deadband_mps")
    validate_max_speed(max_speed)

    left_mps = linear_x - angular_z * wheel_base_m / 2.0
    right_mps = linear_x + angular_z * wheel_base_m / 2.0

    if abs(left_mps) <= deadband_mps and abs(right_mps) <= deadband_mps:
        return WheelCommand(0, 0, should_stop=True, accepted=True, reason="zero_command")

    if left_mps < -deadband_mps or right_mps < -deadband_mps:
        return WheelCommand(
            0,
            0,
            should_stop=True,
            accepted=False,
            reason="reverse_or_pivot_not_verified",
        )

    left = wheel_mps_to_speed(max(0.0, left_mps), max_linear_mps, max_speed)
    right = wheel_mps_to_speed(max(0.0, right_mps), max_linear_mps, max_speed)

    if left == 0 and right == 0:
        return WheelCommand(0, 0, should_stop=True, accepted=True, reason="below_deadband")

    return WheelCommand(left, right, should_stop=False, accepted=True, reason="drive")


def wheel_mps_to_speed(value_mps: float, max_linear_mps: float, max_speed: int) -> int:
    command = round(value_mps / max_linear_mps * max_speed)
    return max(0, min(max_speed, command))


def validate_float(value: float, label: str) -> None:
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ProtocolError(f"{label} must be a finite number")


def validate_positive_float(value: float, label: str) -> None:
    validate_float(value, label)
    if value <= 0:
        raise ProtocolError(f"{label} must be greater than zero")


def validate_max_speed(value: int) -> None:
    if not isinstance(value, int):
        raise ProtocolError("max_speed must be an integer")
    if value <= 0 or value > MAX_DRIVE_SPEED:
        raise ProtocolError(f"max_speed must be between 1 and {MAX_DRIVE_SPEED}")

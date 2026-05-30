"""Conservative ROS2 /cmd_vel conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .protocol import MAX_DRIVE_SPEED, ProtocolError, normalize_steering_direction

DEFAULT_WHEEL_BASE_M = 0.12
DEFAULT_MAX_LINEAR_MPS = 0.35
DEFAULT_DEADBAND_MPS = 0.001
DEFAULT_ANGULAR_DEADBAND_RADPS = 0.001


@dataclass(frozen=True)
class WheelCommand:
    left: int
    right: int
    should_stop: bool
    accepted: bool
    reason: str
    steering: str = "center"


def cmd_vel_to_drive(
    linear_x: float,
    angular_z: float,
    *,
    wheel_base_m: float = DEFAULT_WHEEL_BASE_M,
    max_linear_mps: float = DEFAULT_MAX_LINEAR_MPS,
    max_speed: int = MAX_DRIVE_SPEED,
    deadband_mps: float = DEFAULT_DEADBAND_MPS,
    angular_deadband_radps: float = DEFAULT_ANGULAR_DEADBAND_RADPS,
) -> WheelCommand:
    """Convert planar velocity to current safe Altino wheel commands.

    Physical tests showed Altino Lite does not turn from differential motor
    commands through the current BLE frame. Android Orchestra steering packets
    are verified as discrete left/right/center steering states, so angular
    magnitude currently selects direction only.
    """

    validate_float(linear_x, "linear_x")
    validate_float(angular_z, "angular_z")
    validate_positive_float(wheel_base_m, "wheel_base_m")
    validate_positive_float(max_linear_mps, "max_linear_mps")
    validate_positive_float(deadband_mps, "deadband_mps")
    validate_positive_float(angular_deadband_radps, "angular_deadband_radps")
    validate_max_speed(max_speed)

    if abs(linear_x) <= deadband_mps and abs(angular_z) <= angular_deadband_radps:
        return WheelCommand(0, 0, should_stop=True, accepted=True, reason="zero_command")

    if linear_x < -deadband_mps:
        return WheelCommand(
            0,
            0,
            should_stop=True,
            accepted=False,
            reason="reverse_not_verified",
        )

    speed = wheel_mps_to_speed(max(0.0, linear_x), max_linear_mps, max_speed)

    if abs(angular_z) > angular_deadband_radps:
        steering = angular_z_to_steering(angular_z)
        reason = "steer_drive" if speed else "steer_only"
        return WheelCommand(
            speed,
            speed,
            should_stop=False,
            accepted=True,
            reason=reason,
            steering=steering,
        )

    if speed == 0:
        return WheelCommand(0, 0, should_stop=True, accepted=True, reason="below_deadband")

    return WheelCommand(speed, speed, should_stop=False, accepted=True, reason="drive")


def angular_z_to_steering(angular_z: float) -> str:
    if angular_z > 0:
        return normalize_steering_direction("left")
    return normalize_steering_direction("right")


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

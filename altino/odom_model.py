"""Open-loop command odometry helpers.

This is intentionally command-derived odometry. It integrates the commands that
were sent to Altino, not measured wheel encoder or IMU feedback.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, pi, sin

from .cmd_vel import DEFAULT_MAX_LINEAR_MPS
from .driver_core import DriverEvent
from .protocol import MAX_DRIVE_SPEED, ProtocolError, normalize_steering_direction

ODOM_MODE_OPEN_LOOP_COMMANDED = "open_loop_commanded"

OPEN_LOOP_POSE_COVARIANCE: tuple[float, ...] = (
    10.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    10.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1_000_000.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1_000_000.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1_000_000.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    10.0,
)

OPEN_LOOP_TWIST_COVARIANCE: tuple[float, ...] = (
    1.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    10.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1_000_000.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1_000_000.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    1_000_000.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    10.0,
)


@dataclass(frozen=True)
class Pose2D:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class Twist2D:
    linear_x: float = 0.0
    angular_z: float = 0.0


@dataclass(frozen=True)
class OdomState:
    pose: Pose2D
    twist: Twist2D
    timestamp: float
    mode: str = ODOM_MODE_OPEN_LOOP_COMMANDED


class OpenLoopOdometry:
    """Integrate commanded Altino motion as an explicit open-loop estimate."""

    def __init__(
        self,
        *,
        max_linear_mps: float = DEFAULT_MAX_LINEAR_MPS,
        max_speed: int = MAX_DRIVE_SPEED,
        steering_yaw_rate_radps: float = 0.0,
        initial_time: float = 0.0,
    ) -> None:
        validate_positive_float(max_linear_mps, "max_linear_mps")
        validate_positive_int(max_speed, "max_speed")
        validate_float(steering_yaw_rate_radps, "steering_yaw_rate_radps")
        validate_float(initial_time, "initial_time")

        self.max_linear_mps = max_linear_mps
        self.max_speed = max_speed
        self.steering_yaw_rate_radps = abs(steering_yaw_rate_radps)
        self._pose = Pose2D()
        self._twist = Twist2D()
        self._timestamp = initial_time

    @property
    def state(self) -> OdomState:
        return OdomState(self._pose, self._twist, self._timestamp)

    def reset(
        self,
        *,
        pose: Pose2D | None = None,
        timestamp: float = 0.0,
    ) -> OdomState:
        validate_float(timestamp, "timestamp")
        self._pose = Pose2D() if pose is None else pose
        self._twist = Twist2D()
        self._timestamp = timestamp
        return self.state

    def advance(self, timestamp: float) -> OdomState:
        validate_timestamp(timestamp, self._timestamp)
        dt = timestamp - self._timestamp
        self._pose = integrate_pose(self._pose, self._twist, dt)
        self._timestamp = timestamp
        return self.state

    def handle_event(self, event: DriverEvent, *, timestamp: float) -> OdomState:
        self.advance(timestamp)
        self._twist = event_to_twist(
            event,
            max_linear_mps=self.max_linear_mps,
            max_speed=self.max_speed,
            steering_yaw_rate_radps=self.steering_yaw_rate_radps,
        )
        return self.state


def event_to_twist(
    event: DriverEvent,
    *,
    max_linear_mps: float = DEFAULT_MAX_LINEAR_MPS,
    max_speed: int = MAX_DRIVE_SPEED,
    steering_yaw_rate_radps: float = 0.0,
) -> Twist2D:
    validate_positive_float(max_linear_mps, "max_linear_mps")
    validate_positive_int(max_speed, "max_speed")
    validate_float(steering_yaw_rate_radps, "steering_yaw_rate_radps")

    if event.action == "stop" or not event.accepted:
        return Twist2D()

    if event.action == "drive":
        return Twist2D(
            linear_x=speed_to_mps(
                (event.left + event.right) / 2.0,
                max_linear_mps,
                max_speed,
            )
        )

    if event.action == "steer":
        direction = normalize_steering_direction(event.steering)
        angular_z = steering_direction_to_yaw_rate(direction, steering_yaw_rate_radps)
        return Twist2D(
            linear_x=speed_to_mps(event.left, max_linear_mps, max_speed),
            angular_z=angular_z,
        )

    return Twist2D()


def speed_to_mps(speed: float, max_linear_mps: float, max_speed: int) -> float:
    validate_float(speed, "speed")
    return max(0.0, min(float(max_speed), speed)) / max_speed * max_linear_mps


def steering_direction_to_yaw_rate(direction: str, yaw_rate_radps: float) -> float:
    direction = normalize_steering_direction(direction)
    yaw_rate = abs(yaw_rate_radps)
    if direction == "left":
        return yaw_rate
    if direction == "right":
        return -yaw_rate
    return 0.0


def integrate_pose(pose: Pose2D, twist: Twist2D, dt: float) -> Pose2D:
    validate_nonnegative_float(dt, "dt")
    if dt == 0:
        return pose

    linear = twist.linear_x
    angular = twist.angular_z
    if abs(angular) < 1e-9:
        return Pose2D(
            x=pose.x + linear * dt * cos(pose.yaw),
            y=pose.y + linear * dt * sin(pose.yaw),
            yaw=pose.yaw,
        )

    next_yaw = normalize_angle(pose.yaw + angular * dt)
    radius = linear / angular
    return Pose2D(
        x=pose.x + radius * (sin(next_yaw) - sin(pose.yaw)),
        y=pose.y - radius * (cos(next_yaw) - cos(pose.yaw)),
        yaw=next_yaw,
    )


def normalize_angle(angle: float) -> float:
    validate_float(angle, "angle")
    while angle > pi:
        angle -= 2.0 * pi
    while angle <= -pi:
        angle += 2.0 * pi
    return angle


def validate_timestamp(timestamp: float, previous: float) -> None:
    validate_float(timestamp, "timestamp")
    if timestamp < previous:
        raise ValueError("timestamp must be monotonic")


def validate_float(value: float, label: str) -> None:
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ProtocolError(f"{label} must be a finite number")


def validate_nonnegative_float(value: float, label: str) -> None:
    validate_float(value, label)
    if value < 0:
        raise ProtocolError(f"{label} must be greater than or equal to zero")


def validate_positive_float(value: float, label: str) -> None:
    validate_float(value, label)
    if value <= 0:
        raise ProtocolError(f"{label} must be greater than zero")


def validate_positive_int(value: int, label: str) -> None:
    if not isinstance(value, int):
        raise ProtocolError(f"{label} must be an integer")
    if value <= 0:
        raise ProtocolError(f"{label} must be greater than zero")

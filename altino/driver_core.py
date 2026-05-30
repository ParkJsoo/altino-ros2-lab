"""ROS/BLE-independent Altino driver control flow."""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

from .cmd_vel import (
    DEFAULT_MAX_LINEAR_MPS,
    DEFAULT_WHEEL_BASE_M,
    WheelCommand,
    cmd_vel_to_drive,
)

DEFAULT_CMD_TIMEOUT_S = 0.5


class DriverTransport(Protocol):
    def drive(self, left: int, right: int, reason: str) -> Any:
        """Send a drive command and return the transport-specific operation."""

    def stop(self, reason: str) -> Any:
        """Send a stop command and return the transport-specific operation."""


@dataclass(frozen=True)
class DriverEvent:
    action: str
    reason: str
    accepted: bool
    left: int = 0
    right: int = 0
    operation: Any = None

    @property
    def message(self) -> str:
        if self.action == "drive":
            return f"drive left={self.left} right={self.right} reason={self.reason}"
        return f"stop reason={self.reason}"


@dataclass(frozen=True)
class RecordedCommand:
    action: str
    reason: str
    left: int = 0
    right: int = 0


class RecordingTransport:
    """Fake transport for local tests and dry control-flow checks."""

    def __init__(self) -> None:
        self.commands: list[RecordedCommand] = []

    def drive(self, left: int, right: int, reason: str) -> RecordedCommand:
        command = RecordedCommand("drive", reason, left=left, right=right)
        self.commands.append(command)
        return command

    def stop(self, reason: str) -> RecordedCommand:
        command = RecordedCommand("stop", reason)
        self.commands.append(command)
        return command


class AltinoDriverCore:
    """Small testable state machine shared by ROS2 and fake transports."""

    def __init__(
        self,
        transport: DriverTransport,
        *,
        wheel_base_m: float = DEFAULT_WHEEL_BASE_M,
        max_linear_mps: float = DEFAULT_MAX_LINEAR_MPS,
        cmd_timeout_s: float = DEFAULT_CMD_TIMEOUT_S,
    ) -> None:
        if not isfinite(cmd_timeout_s) or cmd_timeout_s <= 0:
            raise ValueError("cmd_timeout_s must be a finite number greater than zero")

        self.transport = transport
        self.wheel_base_m = wheel_base_m
        self.max_linear_mps = max_linear_mps
        self.cmd_timeout_s = cmd_timeout_s
        self.last_cmd_time = self.now()
        self.stopped = True

    def handle_cmd_vel(
        self,
        linear_x: float,
        angular_z: float,
        *,
        now: float | None = None,
    ) -> DriverEvent:
        timestamp = self.now() if now is None else now
        command = cmd_vel_to_drive(
            linear_x,
            angular_z,
            wheel_base_m=self.wheel_base_m,
            max_linear_mps=self.max_linear_mps,
        )
        self.last_cmd_time = timestamp

        if command.should_stop:
            return self.send_stop(command.reason, accepted=command.accepted)

        return self.send_drive(command)

    def watchdog(self, *, now: float | None = None) -> DriverEvent | None:
        if self.stopped:
            return None

        timestamp = self.now() if now is None else now
        if timestamp - self.last_cmd_time <= self.cmd_timeout_s:
            return None

        return self.send_stop("watchdog_timeout", accepted=True)

    def shutdown(self) -> DriverEvent:
        return self.send_stop("shutdown_stop", accepted=True)

    def send_drive(self, command: WheelCommand) -> DriverEvent:
        operation = self.transport.drive(command.left, command.right, command.reason)
        self.stopped = False
        return DriverEvent(
            "drive",
            command.reason,
            accepted=command.accepted,
            left=command.left,
            right=command.right,
            operation=operation,
        )

    def send_stop(self, reason: str, *, accepted: bool) -> DriverEvent:
        operation = self.transport.stop(reason)
        self.stopped = True
        return DriverEvent("stop", reason, accepted=accepted, operation=operation)

    @staticmethod
    def now() -> float:
        return time.monotonic()

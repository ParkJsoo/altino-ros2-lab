"""Verified Altino Lite BLE frame construction.

The frame shape comes from the Android Orchestra BLE path:

* 22-byte packet
* byte 0: 0x02
* byte 1: 0x10
* byte 2: checksum over bytes 3..20
* byte 21: 0x03
* BLE write is split into 14-byte and 8-byte chunks.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

SERVICE_UUID = "49535343-FE7D-4AE5-8FA9-9FAFD205E455"
NOTIFY_UUID = "49535343-1E4D-4BD9-BA61-23C647249616"
WRITE_UUID = "49535343-8841-43F4-A8D4-ECBE34729BB3"

FRAME_LENGTH = 22
ANDROID_CHUNK_LENGTH = 14

MAX_DRIVE_SPEED = 350
MIN_DRIVE_DURATION = 0.05
MAX_DRIVE_DURATION = 3.0

HORN_ON_VALUE = 0x0F
LIGHT_ON_VALUE = 0x01
STEERING_LEFT_VALUE = 0x80
STEERING_RIGHT_VALUE = 0x7F
STEERING_LEFT_MARKER_VALUE = 0x04
STEERING_RIGHT_MARKER_VALUE = 0x08
STEERING_DIRECTIONS = ("left", "right", "center")


class ProtocolError(ValueError):
    """Raised when a command cannot be encoded safely."""


@dataclass(frozen=True)
class DriveCommand:
    left: int
    right: int
    duration: float

    def validate(self) -> None:
        validate_drive(self.left, self.right, self.duration)


def stop_frame() -> bytes:
    return build_frame()


def light_frame(on: bool) -> bytes:
    return build_frame(light=LIGHT_ON_VALUE if on else 0)


def horn_frame(on: bool) -> bytes:
    return build_frame(sound=HORN_ON_VALUE if on else 0)


def drive_frame(left: int, right: int) -> bytes:
    validate_speed(left, "left")
    validate_speed(right, "right")
    return build_frame(left=left, right=right)


def steering_frame(direction: str, speed: int = 0, *, marker: bool = True) -> bytes:
    """Build a verified Android steering frame.

    Android Orchestra writes steering as byte 5 plus a byte 20 marker. It also
    alternates marker and non-marker frames while the button is held.
    """

    direction = normalize_steering_direction(direction)
    validate_speed(speed, "speed")

    if direction == "center":
        return build_frame(left=speed, right=speed)

    if direction == "left":
        return build_frame(
            steering=STEERING_LEFT_VALUE,
            left=speed,
            right=speed,
            light=STEERING_LEFT_MARKER_VALUE if marker else 0,
        )

    return build_frame(
        steering=STEERING_RIGHT_VALUE,
        left=speed,
        right=speed,
        light=STEERING_RIGHT_MARKER_VALUE if marker else 0,
    )


def validate_drive(left: int, right: int, duration: float) -> None:
    validate_speed(left, "left")
    validate_speed(right, "right")
    validate_duration(duration)


def validate_steering_drive(direction: str, speed: int, duration: float) -> None:
    normalize_steering_direction(direction)
    validate_speed(speed, "speed")
    validate_duration(duration)


def validate_duration(duration: float) -> None:
    if not isinstance(duration, (int, float)) or not isfinite(duration):
        raise ProtocolError("duration must be a finite number")
    if duration < MIN_DRIVE_DURATION or duration > MAX_DRIVE_DURATION:
        raise ProtocolError(
            f"duration must be between {MIN_DRIVE_DURATION:.2f} and "
            f"{MAX_DRIVE_DURATION:.2f} seconds"
        )


def normalize_steering_direction(direction: str) -> str:
    if direction not in STEERING_DIRECTIONS:
        expected = ", ".join(STEERING_DIRECTIONS)
        raise ProtocolError(f"steering direction must be one of: {expected}")
    return direction


def validate_speed(value: int, label: str) -> None:
    if not isinstance(value, int):
        raise ProtocolError(f"{label} speed must be an integer")
    if value < 0 or value > MAX_DRIVE_SPEED:
        raise ProtocolError(f"{label} speed must be between 0 and {MAX_DRIVE_SPEED}")


def build_frame(
    *,
    steering: int = 0,
    right: int = 0,
    left: int = 0,
    sound: int = 0,
    light: int = 0,
) -> bytes:
    validate_byte(steering, "steering")
    validate_motor_for_protocol(right, "right")
    validate_motor_for_protocol(left, "left")
    validate_byte(sound, "sound")
    validate_byte(light, "light")

    frame = bytearray(FRAME_LENGTH)
    frame[0] = 0x02
    frame[1] = 0x10
    frame[3] = 0x01
    frame[4] = 0x01
    frame[5] = steering
    put_motor(frame, 6, right)
    put_motor(frame, 8, left)
    frame[19] = sound
    frame[20] = light
    frame[21] = 0x03
    frame[2] = checksum(frame)
    return bytes(frame)


def android_chunks(frame: bytes) -> tuple[bytes, bytes]:
    if len(frame) != FRAME_LENGTH:
        raise ProtocolError(f"frame must be {FRAME_LENGTH} bytes")
    return frame[:ANDROID_CHUNK_LENGTH], frame[ANDROID_CHUNK_LENGTH:]


def checksum(frame: bytes | bytearray) -> int:
    if len(frame) != FRAME_LENGTH:
        raise ProtocolError(f"frame must be {FRAME_LENGTH} bytes")
    return sum(frame[3:21]) % 256


def put_motor(frame: bytearray, offset: int, value: int) -> None:
    encoded = encode_motor(value)
    frame[offset] = (encoded >> 8) & 0xFF
    frame[offset + 1] = encoded & 0xFF


def encode_motor(value: int) -> int:
    validate_motor_for_protocol(value, "motor")
    if value < 0:
        return (-value) ^ 0xFFFF
    return value


def validate_motor_for_protocol(value: int, label: str) -> None:
    if not isinstance(value, int):
        raise ProtocolError(f"{label} motor value must be an integer")
    if value < -1000 or value > 1000:
        raise ProtocolError(f"{label} motor value must be between -1000 and 1000")


def validate_byte(value: int, label: str) -> None:
    if not isinstance(value, int):
        raise ProtocolError(f"{label} must be an integer")
    if value < 0 or value > 0xFF:
        raise ProtocolError(f"{label} must be between 0 and 255")


def hex_frame(frame: bytes) -> str:
    return " ".join(f"{byte:02x}" for byte in frame)

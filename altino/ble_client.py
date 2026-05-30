"""Async BLE transport for Altino Lite on Linux/Raspberry Pi."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .protocol import (
    WRITE_UUID,
    android_chunks,
    drive_frame,
    horn_frame,
    light_frame,
    steering_frame,
    stop_frame,
    validate_drive,
    validate_steering_drive,
)

STOP_BURST_COUNT = 3
STOP_BURST_INTERVAL = 0.15
CHUNK_INTERVAL = 0.02
STEERING_REPEAT_INTERVAL = 0.12


class BleDependencyError(RuntimeError):
    """Raised when bleak is not installed."""


def load_bleak() -> tuple[Any, Any]:
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as exc:
        raise BleDependencyError(
            "bleak is required for BLE access. Install with: "
            "python3 -m pip install -r requirements-pi.txt"
        ) from exc
    return BleakClient, BleakScanner


@dataclass
class AltinoBleClient:
    address: str | None = None
    name_hint: str = "ALTINO"
    scan_seconds: float = 8.0

    def __post_init__(self) -> None:
        self._client: Any | None = None

    async def __aenter__(self) -> "AltinoBleClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        BleakClient, BleakScanner = load_bleak()

        address = self.address
        if address is None:
            device = await BleakScanner.find_device_by_filter(
                lambda dev, adv: self.name_hint.lower()
                in ((dev.name or adv.local_name or "").lower()),
                timeout=self.scan_seconds,
            )
            if device is None:
                raise RuntimeError(f"Altino device not found with name hint {self.name_hint!r}")
            address = device.address

        self._client = BleakClient(address)
        await self._client.connect()

    async def disconnect(self) -> None:
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()

    async def write_frame(self, frame: bytes, label: str = "frame") -> None:
        if self._client is None or not self._client.is_connected:
            raise RuntimeError("BLE client is not connected")

        for chunk in android_chunks(frame):
            await self._client.write_gatt_char(WRITE_UUID, chunk, response=False)
            await asyncio.sleep(CHUNK_INTERVAL)

    async def stop(self) -> None:
        await self.stop_burst("stop")

    async def light(self, on: bool) -> None:
        await self.write_frame(light_frame(on), "light")

    async def horn(self, on: bool) -> None:
        await self.write_frame(horn_frame(on), "horn")

    async def drive(self, left: int, right: int, duration: float) -> None:
        validate_drive(left, right, duration)
        try:
            await self.write_frame(drive_frame(left, right), "drive")
            await asyncio.sleep(duration)
        finally:
            await self.stop_burst("auto-stop")

    async def steer(self, direction: str, speed: int, duration: float) -> None:
        validate_steering_drive(direction, speed, duration)
        try:
            elapsed = 0.0
            marker = True
            while elapsed < duration:
                await self.write_frame(
                    steering_frame(direction, speed, marker=marker),
                    f"steer-{direction}",
                )
                marker = not marker
                interval = min(STEERING_REPEAT_INTERVAL, duration - elapsed)
                await asyncio.sleep(interval)
                elapsed += interval
        finally:
            await self.stop_burst("steer-auto-stop")

    async def stop_burst(self, label: str) -> None:
        frame = stop_frame()
        for index in range(STOP_BURST_COUNT):
            await self.write_frame(frame, f"{label}-{index + 1}")
            if index < STOP_BURST_COUNT - 1:
                await asyncio.sleep(STOP_BURST_INTERVAL)

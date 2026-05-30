"""Command-line entry point for the Python Altino BLE driver."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from .ble_client import AltinoBleClient, BleDependencyError, load_bleak
from .protocol import (
    ProtocolError,
    android_chunks,
    drive_frame,
    hex_frame,
    horn_frame,
    light_frame,
    stop_frame,
    validate_drive,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        frame = frame_for_args(args)
        if args.dry_run:
            print_frame(frame)
            return 0
        return asyncio.run(run_command(args))
    except (BleDependencyError, ProtocolError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="altino-ble",
        description="Altino Lite BLE control for Linux/Raspberry Pi",
    )
    parser.add_argument("--address", help="BLE address to use instead of scanning")
    parser.add_argument("--name-hint", default="ALTINO", help="device name substring")
    parser.add_argument("--scan-seconds", type=float, default=8.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the verified 22-byte frame and Android split chunks only",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="scan for nearby BLE devices")

    light = sub.add_parser("light", help="turn front light on or off")
    light.add_argument("state", choices=["on", "off"])

    horn = sub.add_parser("horn", help="turn horn on or off")
    horn.add_argument("state", choices=["on", "off"])

    drive = sub.add_parser("drive", help="drive with safe forward-only wheel speeds")
    drive.add_argument("left", type=int)
    drive.add_argument("right", type=int)
    drive.add_argument("seconds", type=float)

    sub.add_parser("stop", help="send a stop burst")
    return parser


def frame_for_args(args: argparse.Namespace) -> bytes | None:
    if args.command == "scan":
        if args.dry_run:
            raise ProtocolError("scan does not support --dry-run")
        return None
    if args.command == "light":
        return light_frame(args.state == "on")
    if args.command == "horn":
        return horn_frame(args.state == "on")
    if args.command == "drive":
        validate_drive(args.left, args.right, args.seconds)
        return drive_frame(args.left, args.right)
    if args.command == "stop":
        return stop_frame()
    raise ProtocolError(f"unknown command: {args.command}")


def print_frame(frame: bytes | None) -> None:
    if frame is None:
        return
    print(f"frame len={len(frame)} {hex_frame(frame)}")
    for index, chunk in enumerate(android_chunks(frame), start=1):
        print(f"chunk {index} len={len(chunk)} {hex_frame(chunk)}")


async def run_command(args: argparse.Namespace) -> int:
    if args.command == "scan":
        await scan(args.name_hint, args.scan_seconds)
        return 0

    client = AltinoBleClient(
        address=args.address,
        name_hint=args.name_hint,
        scan_seconds=args.scan_seconds,
    )
    async with client:
        if args.command == "light":
            await client.light(args.state == "on")
        elif args.command == "horn":
            await client.horn(args.state == "on")
        elif args.command == "drive":
            await client.drive(args.left, args.right, args.seconds)
        elif args.command == "stop":
            await client.stop()
        else:
            raise ProtocolError(f"unknown command: {args.command}")
    return 0


async def scan(name_hint: str, seconds: float) -> None:
    _, BleakScanner = load_bleak()
    devices = await BleakScanner.discover(timeout=seconds, return_adv=True)
    hint = name_hint.lower()
    for device, adv in devices.values():
        name = device.name or adv.local_name or "<unnamed>"
        marker = " altino=yes" if hint in name.lower() else ""
        print(f"name={name} address={device.address} rssi={adv.rssi}{marker}")


if __name__ == "__main__":
    raise SystemExit(main())

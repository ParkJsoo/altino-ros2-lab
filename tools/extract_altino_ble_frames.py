#!/usr/bin/env python3
"""Extract Altino BLE write frames from Android btsnoop logs.

Usage:
  python3 tools/extract_altino_ble_frames.py /path/to/btsnoop_hci.log
  python3 tools/extract_altino_ble_frames.py /path/to/bugreport-directory
  python3 tools/extract_altino_ble_frames.py /path/to/bugreport.zip
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from collections import Counter
from pathlib import Path

DEFAULT_ATT_HANDLE = 0x002D
FRAME_LENGTH = 22
FIRST_CHUNK_LENGTH = 14
SECOND_CHUNK_LENGTH = 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="btsnoop_hci.log, bugreport dir, or zip")
    parser.add_argument(
        "--handle",
        default=f"0x{DEFAULT_ATT_HANDLE:04x}",
        help="ATT write handle to extract, default: 0x002d",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="print every frame instead of collapsed chronological changes",
    )
    args = parser.parse_args()

    handle = int(args.handle, 0)
    data = read_btsnoop(args.input)
    frames = extract_frames(data, handle)

    print(f"frames={len(frames)} handle=0x{handle:04x}")
    counts = Counter(frame for _, frame in frames)
    print(f"unique={len(counts)}")

    for frame, count in counts.most_common():
        print(f"count={count:3d} {hex_bytes(frame)} {describe_frame(frame)}")

    print()
    print("chronological:")
    previous: bytes | None = None
    for record_number, frame in frames:
        if not args.all and frame == previous:
            continue
        previous = frame
        print(f"record={record_number:06d} {hex_bytes(frame)} {describe_frame(frame)}")

    return 0


def read_btsnoop(path: Path) -> bytes:
    if path.is_file() and path.suffix.lower() == ".zip":
        return read_btsnoop_from_zip(path)
    if path.is_dir():
        candidates = list(path.rglob("btsnoop_hci.log"))
        if not candidates:
            raise FileNotFoundError(f"btsnoop_hci.log not found under {path}")
        return candidates[0].read_bytes()
    return path.read_bytes()


def read_btsnoop_from_zip(path: Path) -> bytes:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith("btsnoop_hci.log")]
        if not names:
            raise FileNotFoundError(f"btsnoop_hci.log not found in {path}")
        with archive.open(names[0]) as fp:
            return fp.read()


def extract_frames(data: bytes, handle: int) -> list[tuple[int, bytes]]:
    if data[:8] != b"btsnoop\0":
        raise ValueError("input is not a btsnoop log")

    chunks: list[tuple[int, bytes]] = []
    frames: list[tuple[int, bytes]] = []
    offset = 16
    record_number = 0

    while offset + 24 <= len(data):
        _, included_length, _, _, _ = struct.unpack(">IIIIQ", data[offset : offset + 24])
        offset += 24
        packet = data[offset : offset + included_length]
        offset += included_length
        record_number += 1

        value = att_write_value(packet, handle)
        if value is None:
            continue

        if len(value) == FIRST_CHUNK_LENGTH and value[:2] == b"\x02\x10":
            chunks = [(record_number, value)]
            continue

        if len(value) == SECOND_CHUNK_LENGTH and chunks:
            first_record, first = chunks.pop()
            frame = first + value
            if len(frame) == FRAME_LENGTH:
                frames.append((first_record, frame))
            continue

        chunks = []

    return frames


def att_write_value(packet: bytes, handle: int) -> bytes | None:
    # Android btsnoop uses H4 packets. 0x02 means ACL data.
    if len(packet) < 10 or packet[0] != 0x02:
        return None

    hci_length = int.from_bytes(packet[3:5], "little")
    if len(packet) < 5 + hci_length or hci_length < 5:
        return None

    cid = int.from_bytes(packet[7:9], "little")
    if cid != 4:  # ATT fixed channel
        return None

    att = packet[9 : 5 + hci_length]
    if len(att) < 3:
        return None

    opcode = att[0]
    att_handle = int.from_bytes(att[1:3], "little")
    if opcode != 0x52 or att_handle != handle:
        return None

    return att[3:]


def describe_frame(frame: bytes) -> str:
    if len(frame) != FRAME_LENGTH:
        return ""
    right = int.from_bytes(frame[6:8], "big")
    left = int.from_bytes(frame[8:10], "big")
    fields = [
        f"checksum=0x{frame[2]:02x}",
        f"command=({frame[3]},{frame[4]})",
        f"byte5={frame[5]}",
        f"right_field={right}",
        f"left_field={left}",
        f"byte19={frame[19]}",
        f"byte20={frame[20]}",
    ]
    return "(" + " ".join(fields) + ")"


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02x}" for byte in data)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

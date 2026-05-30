import unittest

from altino.protocol import (
    MAX_DRIVE_SPEED,
    ProtocolError,
    android_chunks,
    checksum,
    drive_frame,
    hex_frame,
    horn_frame,
    light_frame,
    stop_frame,
    validate_drive,
)


class ProtocolTest(unittest.TestCase):
    def test_stop_frame_matches_android_capture(self) -> None:
        self.assertEqual(
            hex_frame(stop_frame()),
            "02 10 02 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 03",
        )

    def test_light_on_frame_matches_android_capture(self) -> None:
        self.assertEqual(
            hex_frame(light_frame(True)),
            "02 10 03 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 03",
        )

    def test_horn_on_sets_sound_with_motors_stopped(self) -> None:
        frame = horn_frame(True)
        self.assertEqual(frame[19], 0x0F)
        self.assertEqual(frame[6:10], b"\x00\x00\x00\x00")
        self.assertEqual(frame[2], checksum(frame))

    def test_drive_frame_encodes_right_then_left_motors(self) -> None:
        frame = drive_frame(left=100, right=200)
        self.assertEqual(frame[6:8], b"\x00\xc8")
        self.assertEqual(frame[8:10], b"\x00\x64")
        self.assertEqual(frame[2], checksum(frame))

    def test_android_chunks_are_14_then_8_bytes(self) -> None:
        first, second = android_chunks(light_frame(True))
        self.assertEqual(len(first), 14)
        self.assertEqual(len(second), 8)
        self.assertEqual(first + second, light_frame(True))

    def test_drive_validation_rejects_reverse_until_verified(self) -> None:
        with self.assertRaises(ProtocolError):
            drive_frame(left=-1, right=0)

    def test_drive_validation_rejects_above_safe_limit(self) -> None:
        with self.assertRaises(ProtocolError):
            drive_frame(left=0, right=MAX_DRIVE_SPEED + 1)

    def test_drive_validation_checks_duration(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_drive(left=100, right=100, duration=3.01)

        with self.assertRaises(ProtocolError):
            validate_drive(left=100, right=100, duration=float("nan"))


if __name__ == "__main__":
    unittest.main()

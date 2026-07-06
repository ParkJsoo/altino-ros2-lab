import unittest

from altino.cmd_vel import cmd_vel_to_drive
from altino.protocol import ProtocolError


class CmdVelTest(unittest.TestCase):
    def test_zero_command_requests_stop(self) -> None:
        command = cmd_vel_to_drive(0.0, 0.0)
        self.assertTrue(command.should_stop)
        self.assertTrue(command.accepted)
        self.assertEqual(command.left, 0)
        self.assertEqual(command.right, 0)

    def test_forward_command_maps_to_equal_wheel_speeds(self) -> None:
        command = cmd_vel_to_drive(0.5, 0.0, max_linear_mps=1.0, max_speed=100)
        self.assertFalse(command.should_stop)
        self.assertEqual(command.left, 50)
        self.assertEqual(command.right, 50)

    def test_default_stable_forward_speed_maps_to_verified_threshold(self) -> None:
        command = cmd_vel_to_drive(0.30, 0.0)
        self.assertFalse(command.should_stop)
        self.assertEqual(command.reason, "drive")
        self.assertEqual((command.left, command.right), (300, 300))

    def test_forward_command_above_limit_is_clamped_and_reported(self) -> None:
        command = cmd_vel_to_drive(2.0, 0.0, max_linear_mps=1.0, max_speed=100)

        self.assertFalse(command.should_stop)
        self.assertEqual(command.reason, "drive_limited")
        self.assertEqual((command.left, command.right), (100, 100))

    def test_positive_angular_command_maps_to_left_steer_drive(self) -> None:
        command = cmd_vel_to_drive(
            0.5,
            1.0,
            wheel_base_m=0.5,
            max_linear_mps=1.0,
            max_speed=100,
        )
        self.assertFalse(command.should_stop)
        self.assertTrue(command.accepted)
        self.assertEqual(command.reason, "steer_drive")
        self.assertEqual(command.steering, "left")
        self.assertEqual((command.left, command.right), (50, 50))

    def test_negative_angular_command_maps_to_right_steer_drive(self) -> None:
        command = cmd_vel_to_drive(
            0.5,
            -1.0,
            wheel_base_m=0.5,
            max_linear_mps=1.0,
            max_speed=100,
        )
        self.assertFalse(command.should_stop)
        self.assertTrue(command.accepted)
        self.assertEqual(command.reason, "steer_drive")
        self.assertEqual(command.steering, "right")
        self.assertEqual((command.left, command.right), (50, 50))

    def test_angular_command_above_linear_limit_is_clamped_and_reported(self) -> None:
        command = cmd_vel_to_drive(2.0, 1.0, max_linear_mps=1.0, max_speed=100)

        self.assertFalse(command.should_stop)
        self.assertEqual(command.reason, "steer_drive_limited")
        self.assertEqual(command.steering, "left")
        self.assertEqual((command.left, command.right), (100, 100))

    def test_pivot_command_maps_to_stationary_steering(self) -> None:
        command = cmd_vel_to_drive(0.0, 1.0)
        self.assertFalse(command.should_stop)
        self.assertTrue(command.accepted)
        self.assertEqual(command.reason, "steer_only")
        self.assertEqual(command.steering, "left")
        self.assertEqual((command.left, command.right), (0, 0))

    def test_reverse_is_rejected_until_verified(self) -> None:
        command = cmd_vel_to_drive(-0.1, 0.0)
        self.assertTrue(command.should_stop)
        self.assertFalse(command.accepted)
        self.assertEqual(command.reason, "reverse_not_verified")

    def test_non_finite_velocity_is_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            cmd_vel_to_drive(float("nan"), 0.0)


if __name__ == "__main__":
    unittest.main()

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

    def test_forward_turn_keeps_differential_wheel_speeds(self) -> None:
        command = cmd_vel_to_drive(
            0.5,
            1.0,
            wheel_base_m=0.5,
            max_linear_mps=1.0,
            max_speed=100,
        )
        self.assertFalse(command.should_stop)
        self.assertEqual(command.left, 25)
        self.assertEqual(command.right, 75)

    def test_pivot_is_rejected_until_reverse_is_verified(self) -> None:
        command = cmd_vel_to_drive(0.0, 1.0)
        self.assertTrue(command.should_stop)
        self.assertFalse(command.accepted)
        self.assertEqual(command.reason, "reverse_or_pivot_not_verified")

    def test_reverse_is_rejected_until_verified(self) -> None:
        command = cmd_vel_to_drive(-0.1, 0.0)
        self.assertTrue(command.should_stop)
        self.assertFalse(command.accepted)

    def test_non_finite_velocity_is_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            cmd_vel_to_drive(float("nan"), 0.0)


if __name__ == "__main__":
    unittest.main()

import importlib
import unittest

from altino.driver_core import DriverEvent
from altino.odom_model import (
    OPEN_LOOP_POSE_COVARIANCE,
    OPEN_LOOP_TWIST_COVARIANCE,
    OpenLoopOdometry,
    Pose2D,
    Twist2D,
    event_to_twist,
    integrate_pose,
)


class OdomModelTest(unittest.TestCase):
    def test_covariances_match_ros_odom_shape(self) -> None:
        self.assertEqual(len(OPEN_LOOP_POSE_COVARIANCE), 36)
        self.assertEqual(len(OPEN_LOOP_TWIST_COVARIANCE), 36)
        self.assertGreater(OPEN_LOOP_POSE_COVARIANCE[14], 1000)
        self.assertGreater(OPEN_LOOP_TWIST_COVARIANCE[14], 1000)

    def test_drive_event_sets_open_loop_forward_twist(self) -> None:
        event = DriverEvent("drive", "drive", accepted=True, left=300, right=300)

        twist = event_to_twist(event)

        self.assertAlmostEqual(twist.linear_x, 0.30)
        self.assertEqual(twist.angular_z, 0.0)

    def test_stop_event_clears_twist(self) -> None:
        event = DriverEvent("stop", "watchdog_timeout", accepted=True)

        twist = event_to_twist(event)

        self.assertEqual(twist, Twist2D())

    def test_rejected_event_clears_twist(self) -> None:
        event = DriverEvent("stop", "reverse_not_verified", accepted=False)

        twist = event_to_twist(event)

        self.assertEqual(twist, Twist2D())

    def test_open_loop_odometry_integrates_previous_command_until_next_event(self) -> None:
        odom = OpenLoopOdometry(initial_time=10.0)
        odom.handle_event(
            DriverEvent("drive", "drive", accepted=True, left=300, right=300),
            timestamp=10.0,
        )

        state = odom.advance(11.0)

        self.assertAlmostEqual(state.pose.x, 0.30)
        self.assertAlmostEqual(state.pose.y, 0.0)
        self.assertAlmostEqual(state.pose.yaw, 0.0)

        state = odom.handle_event(
            DriverEvent("stop", "zero_command", accepted=True),
            timestamp=11.5,
        )

        self.assertAlmostEqual(state.pose.x, 0.45)
        self.assertEqual(state.twist, Twist2D())

    def test_steering_does_not_integrate_yaw_until_calibrated(self) -> None:
        odom = OpenLoopOdometry(initial_time=0.0)
        odom.handle_event(
            DriverEvent(
                "steer",
                "steer_drive",
                accepted=True,
                left=300,
                right=300,
                steering="left",
            ),
            timestamp=0.0,
        )

        state = odom.advance(1.0)

        self.assertAlmostEqual(state.pose.x, 0.30)
        self.assertAlmostEqual(state.pose.y, 0.0)
        self.assertAlmostEqual(state.pose.yaw, 0.0)
        self.assertAlmostEqual(state.twist.angular_z, 0.0)

    def test_configured_steering_yaw_rate_integrates_arc(self) -> None:
        odom = OpenLoopOdometry(initial_time=0.0, steering_yaw_rate_radps=0.5)
        odom.handle_event(
            DriverEvent(
                "steer",
                "steer_drive",
                accepted=True,
                left=300,
                right=300,
                steering="left",
            ),
            timestamp=0.0,
        )

        state = odom.advance(1.0)

        self.assertAlmostEqual(state.pose.yaw, 0.5)
        self.assertGreater(state.pose.x, 0.0)
        self.assertGreater(state.pose.y, 0.0)
        self.assertAlmostEqual(state.twist.angular_z, 0.5)

    def test_integrate_pose_keeps_angle_normalized(self) -> None:
        pose = integrate_pose(Pose2D(yaw=3.0), Twist2D(angular_z=1.0), 1.0)

        self.assertGreaterEqual(pose.yaw, -3.141592654)
        self.assertLessEqual(pose.yaw, 3.141592654)

    def test_rejects_non_monotonic_time(self) -> None:
        odom = OpenLoopOdometry(initial_time=2.0)

        with self.assertRaises(ValueError):
            odom.advance(1.0)

    def test_ros2_driver_import_does_not_require_ros2(self) -> None:
        module = importlib.import_module("altino.ros2_driver")

        self.assertTrue(hasattr(module, "main"))


if __name__ == "__main__":
    unittest.main()

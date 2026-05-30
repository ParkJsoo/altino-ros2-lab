import unittest

from altino.driver_core import AltinoDriverCore, RecordingTransport


class DriverCoreTest(unittest.TestCase):
    def test_forward_cmd_vel_sends_drive(self) -> None:
        transport = RecordingTransport()
        core = AltinoDriverCore(
            transport,
            wheel_base_m=0.5,
            max_linear_mps=1.0,
            cmd_timeout_s=0.5,
        )

        event = core.handle_cmd_vel(0.5, 0.0, now=10.0)

        self.assertEqual(event.action, "drive")
        self.assertTrue(event.accepted)
        self.assertEqual((event.left, event.right), (175, 175))
        self.assertFalse(core.stopped)
        self.assertEqual(transport.commands[-1].action, "drive")

    def test_forward_turn_sends_differential_drive(self) -> None:
        transport = RecordingTransport()
        core = AltinoDriverCore(
            transport,
            wheel_base_m=0.5,
            max_linear_mps=1.0,
            cmd_timeout_s=0.5,
        )

        event = core.handle_cmd_vel(0.5, 1.0, now=10.0)

        self.assertEqual(event.action, "drive")
        self.assertEqual((event.left, event.right), (88, 262))
        self.assertEqual((transport.commands[-1].left, transport.commands[-1].right), (88, 262))

    def test_zero_cmd_vel_sends_stop(self) -> None:
        transport = RecordingTransport()
        core = AltinoDriverCore(transport)

        event = core.handle_cmd_vel(0.0, 0.0, now=10.0)

        self.assertEqual(event.action, "stop")
        self.assertTrue(event.accepted)
        self.assertEqual(event.reason, "zero_command")
        self.assertTrue(core.stopped)

    def test_reverse_cmd_vel_is_rejected_and_stops(self) -> None:
        transport = RecordingTransport()
        core = AltinoDriverCore(transport)

        event = core.handle_cmd_vel(-0.1, 0.0, now=10.0)

        self.assertEqual(event.action, "stop")
        self.assertFalse(event.accepted)
        self.assertEqual(event.reason, "reverse_or_pivot_not_verified")
        self.assertEqual(transport.commands[-1].action, "stop")

    def test_watchdog_stops_once_after_timeout(self) -> None:
        transport = RecordingTransport()
        core = AltinoDriverCore(
            transport,
            wheel_base_m=0.5,
            max_linear_mps=1.0,
            cmd_timeout_s=0.5,
        )
        core.handle_cmd_vel(0.5, 0.0, now=10.0)

        self.assertIsNone(core.watchdog(now=10.5))
        event = core.watchdog(now=10.51)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.action, "stop")
        self.assertEqual(event.reason, "watchdog_timeout")
        self.assertTrue(core.stopped)

        self.assertIsNone(core.watchdog(now=11.5))
        self.assertEqual([command.action for command in transport.commands], ["drive", "stop"])

    def test_shutdown_sends_stop(self) -> None:
        transport = RecordingTransport()
        core = AltinoDriverCore(transport)

        event = core.shutdown()

        self.assertEqual(event.action, "stop")
        self.assertEqual(event.reason, "shutdown_stop")
        self.assertEqual(transport.commands[-1].action, "stop")


if __name__ == "__main__":
    unittest.main()

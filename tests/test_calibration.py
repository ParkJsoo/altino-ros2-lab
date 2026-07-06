import io
import unittest

from altino.calibration import (
    format_summary,
    parse_trials,
    summarize_trials,
)


class CalibrationTest(unittest.TestCase):
    def test_summarizes_manual_trials(self) -> None:
        trials = parse_trials(
            io.StringIO(
                "\n".join(
                    [
                        "trial,mode,command_linear_x,command_angular_z,duration_s,distance_m,yaw_deg,notes",
                        "straight_1,straight,0.30,0.0,2.0,0.50,0.0,",
                        "straight_2,straight,0.30,0.0,2.0,0.46,0.0,",
                        "left_1,steer_left,0.30,0.5,2.0,0.40,60.0,",
                        "right_1,steer_right,0.30,-0.5,2.0,0.38,54.0,",
                    ]
                )
            )
        )

        summary = summarize_trials(trials)

        self.assertIsNotNone(summary.linear)
        assert summary.linear is not None
        self.assertEqual(summary.linear.trial_count, 2)
        self.assertAlmostEqual(summary.linear.average_measured_mps, 0.24)
        self.assertAlmostEqual(summary.linear.recommended_max_linear_mps, 0.28)

        self.assertIsNotNone(summary.steering_left)
        self.assertIsNotNone(summary.steering_right)
        assert summary.steering_left is not None
        assert summary.steering_right is not None
        self.assertAlmostEqual(summary.steering_left.average_yaw_rate_radps, 0.5235987756)
        self.assertAlmostEqual(summary.steering_right.average_yaw_rate_radps, 0.4712388980)

    def test_format_summary_includes_config_candidates(self) -> None:
        trials = parse_trials(
            io.StringIO(
                "\n".join(
                    [
                        "trial,mode,command_linear_x,command_angular_z,duration_s,distance_m,yaw_deg,notes",
                        "straight_1,straight,0.30,0.0,2.0,0.60,0.0,",
                        "left_1,steer_left,0.30,0.5,2.0,0.40,60.0,",
                        "right_1,steer_right,0.30,-0.5,2.0,0.40,60.0,",
                    ]
                )
            )
        )

        text = format_summary(summarize_trials(trials))

        self.assertIn("recommended max_linear_mps", text)
        self.assertIn("recommended steering_yaw_rate_radps", text)


if __name__ == "__main__":
    unittest.main()

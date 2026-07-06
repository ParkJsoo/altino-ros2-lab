"""Manual calibration helpers for pre-sensor Altino bring-up."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .cmd_vel import DEFAULT_MAX_LINEAR_MPS, wheel_mps_to_speed
from .protocol import MAX_DRIVE_SPEED, ProtocolError

STRAIGHT_MODE = "straight"
STEER_LEFT_MODE = "steer_left"
STEER_RIGHT_MODE = "steer_right"
CALIBRATION_MODES = {STRAIGHT_MODE, STEER_LEFT_MODE, STEER_RIGHT_MODE}


@dataclass(frozen=True)
class CalibrationTrial:
    trial: str
    mode: str
    command_linear_x: float
    command_angular_z: float
    duration_s: float
    distance_m: float
    yaw_deg: float
    notes: str = ""

    @property
    def measured_linear_mps(self) -> float:
        return self.distance_m / self.duration_s

    @property
    def measured_yaw_rate_radps(self) -> float:
        return math.radians(abs(self.yaw_deg)) / self.duration_s


@dataclass(frozen=True)
class LinearCalibration:
    trial_count: int
    average_measured_mps: float
    recommended_max_linear_mps: float


@dataclass(frozen=True)
class SteeringCalibration:
    trial_count: int
    average_yaw_rate_radps: float


@dataclass(frozen=True)
class CalibrationSummary:
    linear: LinearCalibration | None
    steering_left: SteeringCalibration | None
    steering_right: SteeringCalibration | None


def load_trials(path: Path) -> list[CalibrationTrial]:
    with path.open(newline="", encoding="utf-8") as handle:
        return parse_trials(handle)


def parse_trials(rows: Iterable[str]) -> list[CalibrationTrial]:
    reader = csv.DictReader(rows)
    required = {
        "trial",
        "mode",
        "command_linear_x",
        "command_angular_z",
        "duration_s",
        "distance_m",
        "yaw_deg",
        "notes",
    }
    missing = required.difference(reader.fieldnames or [])
    if missing:
        raise ProtocolError(f"missing calibration columns: {', '.join(sorted(missing))}")

    trials: list[CalibrationTrial] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        trial = CalibrationTrial(
            trial=(row["trial"] or "").strip(),
            mode=parse_mode(row["mode"], row_number),
            command_linear_x=parse_float(row["command_linear_x"], "command_linear_x", row_number),
            command_angular_z=parse_float(row["command_angular_z"], "command_angular_z", row_number),
            duration_s=parse_positive_float(row["duration_s"], "duration_s", row_number),
            distance_m=parse_nonnegative_float(row["distance_m"], "distance_m", row_number),
            yaw_deg=parse_float(row["yaw_deg"], "yaw_deg", row_number),
            notes=(row["notes"] or "").strip(),
        )
        trials.append(trial)

    if not trials:
        raise ProtocolError("calibration file has no trial rows")
    return trials


def summarize_trials(
    trials: Sequence[CalibrationTrial],
    *,
    current_max_linear_mps: float = DEFAULT_MAX_LINEAR_MPS,
) -> CalibrationSummary:
    if current_max_linear_mps <= 0:
        raise ProtocolError("current_max_linear_mps must be greater than zero")

    return CalibrationSummary(
        linear=summarize_linear(trials, current_max_linear_mps=current_max_linear_mps),
        steering_left=summarize_steering(trials, STEER_LEFT_MODE),
        steering_right=summarize_steering(trials, STEER_RIGHT_MODE),
    )


def summarize_linear(
    trials: Sequence[CalibrationTrial],
    *,
    current_max_linear_mps: float,
) -> LinearCalibration | None:
    straight_trials = [trial for trial in trials if trial.mode == STRAIGHT_MODE]
    if not straight_trials:
        return None

    measured = [trial.measured_linear_mps for trial in straight_trials]
    recommendations = [
        recommended_max_linear_mps(trial, current_max_linear_mps=current_max_linear_mps)
        for trial in straight_trials
    ]
    return LinearCalibration(
        trial_count=len(straight_trials),
        average_measured_mps=average(measured),
        recommended_max_linear_mps=average(recommendations),
    )


def summarize_steering(
    trials: Sequence[CalibrationTrial],
    mode: str,
) -> SteeringCalibration | None:
    steering_trials = [trial for trial in trials if trial.mode == mode]
    if not steering_trials:
        return None

    return SteeringCalibration(
        trial_count=len(steering_trials),
        average_yaw_rate_radps=average(
            [trial.measured_yaw_rate_radps for trial in steering_trials]
        ),
    )


def recommended_max_linear_mps(
    trial: CalibrationTrial,
    *,
    current_max_linear_mps: float,
) -> float:
    speed = wheel_mps_to_speed(
        trial.command_linear_x,
        current_max_linear_mps,
        MAX_DRIVE_SPEED,
    )
    if speed <= 0:
        raise ProtocolError(
            f"trial {trial.trial or '<unnamed>'} cannot calibrate with zero motor speed"
        )
    return trial.measured_linear_mps * MAX_DRIVE_SPEED / speed


def format_summary(summary: CalibrationSummary) -> str:
    lines: list[str] = []
    if summary.linear is None:
        lines.append("linear: no straight trials")
    else:
        lines.extend(
            [
                f"linear trials: {summary.linear.trial_count}",
                f"average measured linear speed: {summary.linear.average_measured_mps:.4f} m/s",
                f"recommended max_linear_mps: {summary.linear.recommended_max_linear_mps:.4f}",
            ]
        )

    for label, result in (
        ("left steering", summary.steering_left),
        ("right steering", summary.steering_right),
    ):
        if result is None:
            lines.append(f"{label}: no trials")
        else:
            lines.append(
                f"{label} trials: {result.trial_count}, "
                f"average yaw rate: {result.average_yaw_rate_radps:.4f} rad/s"
            )

    if summary.steering_left and summary.steering_right:
        combined = average(
            [
                summary.steering_left.average_yaw_rate_radps,
                summary.steering_right.average_yaw_rate_radps,
            ]
        )
        lines.append(f"recommended steering_yaw_rate_radps: {combined:.4f}")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="altino-calibration",
        description="Summarize manual Altino calibration CSV trials.",
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--current-max-linear-mps",
        type=float,
        default=DEFAULT_MAX_LINEAR_MPS,
        help="max_linear_mps used when the trials were recorded",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        trials = load_trials(args.csv_path)
        summary = summarize_trials(
            trials,
            current_max_linear_mps=args.current_max_linear_mps,
        )
    except (OSError, ProtocolError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(format_summary(summary))
    return 0


def parse_mode(value: str | None, row_number: int) -> str:
    mode = (value or "").strip()
    if mode not in CALIBRATION_MODES:
        raise ProtocolError(
            f"row {row_number}: mode must be one of {', '.join(sorted(CALIBRATION_MODES))}"
        )
    return mode


def parse_float(value: str | None, label: str, row_number: int) -> float:
    try:
        number = float((value or "").strip())
    except ValueError as exc:
        raise ProtocolError(f"row {row_number}: {label} must be a number") from exc
    if not math.isfinite(number):
        raise ProtocolError(f"row {row_number}: {label} must be finite")
    return number


def parse_positive_float(value: str | None, label: str, row_number: int) -> float:
    number = parse_float(value, label, row_number)
    if number <= 0:
        raise ProtocolError(f"row {row_number}: {label} must be greater than zero")
    return number


def parse_nonnegative_float(value: str | None, label: str, row_number: int) -> float:
    number = parse_float(value, label, row_number)
    if number < 0:
        raise ProtocolError(f"row {row_number}: {label} must be non-negative")
    return number


def average(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty sequence")
    return sum(values) / len(values)


if __name__ == "__main__":
    raise SystemExit(main())

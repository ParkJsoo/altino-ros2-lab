"""Standalone launch wrapper for the Altino driver module."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, ThisLaunchFileDir

DRIVER_WRAPPER = (
    'python3 -m altino.ros2_driver --ros-args --params-file "$1" & '
    "child=$!; "
    "trap 'kill -TERM \"$child\" 2>/dev/null; wait \"$child\" 2>/dev/null; exit 0' "
    "INT TERM; "
    'wait "$child"'
)


def generate_launch_description() -> LaunchDescription:
    params_file = LaunchConfiguration("params_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value=PathJoinSubstitution(
                    [ThisLaunchFileDir(), "..", "config", "altino_driver.yaml"]
                ),
                description="Path to the Altino driver ROS2 parameter file.",
            ),
            ExecuteProcess(
                cmd=[
                    "bash",
                    "-lc",
                    DRIVER_WRAPPER,
                    "altino-driver-wrapper",
                    params_file,
                ],
                output="screen",
            ),
        ]
    )

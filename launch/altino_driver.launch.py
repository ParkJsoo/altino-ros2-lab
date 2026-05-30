"""Standalone launch wrapper for the Altino driver module."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, ThisLaunchFileDir


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
                    "python3",
                    "-m",
                    "altino.ros2_driver",
                    "--ros-args",
                    "--params-file",
                    params_file,
                ],
                output="screen",
            ),
        ]
    )

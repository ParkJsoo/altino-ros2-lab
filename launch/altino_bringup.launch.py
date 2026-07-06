"""Bring up the Altino driver, robot model, and optional RViz view."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
    ThisLaunchFileDir,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

DRIVER_WRAPPER = (
    'python3 -m altino.ros2_driver --ros-args --params-file "$1" & '
    "child=$!; "
    "trap 'kill -TERM \"$child\" 2>/dev/null; wait \"$child\" 2>/dev/null; exit 0' "
    "INT TERM; "
    'wait "$child"'
)


def generate_launch_description() -> LaunchDescription:
    params_file = LaunchConfiguration("params_file")
    model_file = LaunchConfiguration("model_file")
    rviz_config = LaunchConfiguration("rviz_config")
    start_driver = LaunchConfiguration("start_driver")
    start_robot_state_publisher = LaunchConfiguration("start_robot_state_publisher")
    start_rviz = LaunchConfiguration("rviz")
    include_sensor_placeholders = LaunchConfiguration("include_sensor_placeholders")

    robot_description = ParameterValue(
        Command(
            [
                FindExecutable(name="xacro"),
                " ",
                model_file,
                " include_sensor_placeholders:=",
                include_sensor_placeholders,
            ]
        ),
        value_type=str,
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value=PathJoinSubstitution(
                    [ThisLaunchFileDir(), "..", "config", "altino_driver.yaml"]
                ),
                description="Path to the Altino driver ROS2 parameter file.",
            ),
            DeclareLaunchArgument(
                "model_file",
                default_value=PathJoinSubstitution(
                    [ThisLaunchFileDir(), "..", "description", "altino_lite.urdf.xacro"]
                ),
                description="Path to the Altino URDF/xacro model.",
            ),
            DeclareLaunchArgument(
                "rviz_config",
                default_value=PathJoinSubstitution(
                    [ThisLaunchFileDir(), "..", "config", "altino_odom_tf.rviz"]
                ),
                description="Path to the RViz configuration.",
            ),
            DeclareLaunchArgument(
                "start_driver",
                default_value="true",
                description="Start the BLE-backed Altino ROS2 driver.",
            ),
            DeclareLaunchArgument(
                "start_robot_state_publisher",
                default_value="true",
                description="Start robot_state_publisher from the xacro model.",
            ),
            DeclareLaunchArgument(
                "include_sensor_placeholders",
                default_value="false",
                description="Include planned IMU/range/LiDAR placeholder frames in the robot model.",
            ),
            DeclareLaunchArgument(
                "rviz",
                default_value="false",
                description="Start RViz with the odom/TF/robot-model view.",
            ),
            Node(
                condition=IfCondition(start_robot_state_publisher),
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="robot_state_publisher",
                output="screen",
                parameters=[{"robot_description": robot_description}],
            ),
            ExecuteProcess(
                condition=IfCondition(start_driver),
                cmd=[
                    "bash",
                    "-lc",
                    DRIVER_WRAPPER,
                    "altino-driver-wrapper",
                    params_file,
                ],
                output="screen",
            ),
            ExecuteProcess(
                condition=IfCondition(start_rviz),
                cmd=["rviz2", "-d", rviz_config],
                output="screen",
            ),
        ]
    )

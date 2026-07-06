"""Optional ROS2 driver node for Altino Lite.

This module keeps ROS2 imports inside ``main`` so protocol and CLI tests can run
on machines without ROS2 installed.
"""

from __future__ import annotations

import asyncio
import signal
import sys
import threading
from collections.abc import Sequence
from concurrent.futures import Future
from math import cos, sin

from .ble_client import AltinoBleClient
from .cmd_vel import (
    DEFAULT_MAX_LINEAR_MPS,
    DEFAULT_WHEEL_BASE_M,
)
from .driver_core import DEFAULT_CMD_TIMEOUT_S, AltinoDriverCore, DriverEvent
from .odom_model import (
    ODOM_MODE_OPEN_LOOP_COMMANDED,
    OPEN_LOOP_POSE_COVARIANCE,
    OPEN_LOOP_TWIST_COVARIANCE,
    OpenLoopOdometry,
    OdomState,
)
from .protocol import drive_frame, steering_frame

SHUTDOWN_OPERATION_TIMEOUT_S = 1.0
SHUTDOWN_JOIN_TIMEOUT_S = 1.0
DEFAULT_ODOM_PUBLISH_HZ = 10.0


def set_yaw_orientation(orientation: object, yaw: float) -> None:
    half_yaw = yaw * 0.5
    orientation.x = 0.0
    orientation.y = 0.0
    orientation.z = sin(half_yaw)
    orientation.w = cos(half_yaw)


class AsyncBleWorker:
    def __init__(self, *, address: str | None, name_hint: str, scan_seconds: float) -> None:
        self.client = AltinoBleClient(
            address=address,
            name_hint=name_hint,
            scan_seconds=scan_seconds,
        )
        self.loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="altino-ble", daemon=True)
        self._steering_marker = True
        self._last_steering_direction: str | None = None

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def connect(self) -> Future[None]:
        return self.submit(self.client.connect())

    def write_drive(self, left: int, right: int) -> Future[None]:
        self._last_steering_direction = None
        self._steering_marker = True
        return self.submit(self.client.write_frame(drive_frame(left, right), "cmd_vel"))

    def write_steer(self, direction: str, speed: int) -> Future[None]:
        if direction != self._last_steering_direction:
            self._steering_marker = True
            self._last_steering_direction = direction

        frame = steering_frame(direction, speed, marker=self._steering_marker)
        self._steering_marker = not self._steering_marker
        return self.submit(self.client.write_frame(frame, f"cmd_vel-steer-{direction}"))

    def stop(self, reason: str) -> Future[None]:
        self._last_steering_direction = None
        self._steering_marker = True
        return self.submit(self.client.stop_burst(reason))

    def shutdown(self) -> None:
        if self._ready.is_set():
            try:
                self.stop("shutdown-stop").result(timeout=SHUTDOWN_OPERATION_TIMEOUT_S)
            except Exception:
                pass
            try:
                self.submit(self.client.disconnect()).result(timeout=SHUTDOWN_OPERATION_TIMEOUT_S)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._thread.join(timeout=SHUTDOWN_JOIN_TIMEOUT_S)

    def submit(self, coroutine: object) -> Future[None]:
        if not self._ready.is_set():
            raise RuntimeError("BLE worker loop is not ready")
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        self.loop.run_forever()
        self.loop.close()


class WorkerTransport:
    def __init__(self, worker: AsyncBleWorker) -> None:
        self.worker = worker

    def drive(self, left: int, right: int, reason: str) -> Future[None]:
        return self.worker.write_drive(left, right)

    def steer(self, direction: str, speed: int, reason: str) -> Future[None]:
        return self.worker.write_steer(direction, speed)

    def stop(self, reason: str) -> Future[None]:
        return self.worker.stop(reason)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        import rclpy
        from geometry_msgs.msg import TransformStamped, Twist
        from nav_msgs.msg import Odometry
        from rclpy.executors import ExternalShutdownException
        from rclpy.node import Node
        from std_msgs.msg import Bool, String
        from std_srvs.srv import Trigger
        from tf2_ros import TransformBroadcaster
    except ImportError as exc:
        print(
            "error: ROS2 Python packages are required. Source a ROS2 environment "
            "that provides rclpy, geometry_msgs, nav_msgs, std_msgs, std_srvs, "
            "and tf2_ros.",
            file=sys.stderr,
        )
        print(f"detail: {exc}", file=sys.stderr)
        return 2

    class AltinoDriverNode(Node):
        def __init__(self) -> None:
            super().__init__("altino_driver")

            self.declare_parameter("address", "")
            self.declare_parameter("name_hint", "ALTINO")
            self.declare_parameter("scan_seconds", 8.0)
            self.declare_parameter("wheel_base_m", DEFAULT_WHEEL_BASE_M)
            self.declare_parameter("max_linear_mps", DEFAULT_MAX_LINEAR_MPS)
            self.declare_parameter("cmd_timeout_s", DEFAULT_CMD_TIMEOUT_S)
            self.declare_parameter("cmd_vel_topic", "cmd_vel")
            self.declare_parameter("driver_state_topic", "driver_state")
            self.declare_parameter("emergency_stop_topic", "emergency_stop")
            self.declare_parameter("clear_emergency_stop_service", "clear_emergency_stop")
            self.declare_parameter("odom_topic", "odom")
            self.declare_parameter("odom_frame_id", "odom")
            self.declare_parameter("base_frame_id", "base_footprint")
            self.declare_parameter("odom_mode", ODOM_MODE_OPEN_LOOP_COMMANDED)
            self.declare_parameter("publish_odom", True)
            self.declare_parameter("publish_tf", True)
            self.declare_parameter("odom_publish_hz", DEFAULT_ODOM_PUBLISH_HZ)
            self.declare_parameter("steering_yaw_rate_radps", 0.0)

            address = self.get_parameter("address").value or None
            name_hint = str(self.get_parameter("name_hint").value)
            scan_seconds = float(self.get_parameter("scan_seconds").value)

            wheel_base_m = float(self.get_parameter("wheel_base_m").value)
            max_linear_mps = float(self.get_parameter("max_linear_mps").value)
            cmd_timeout_s = float(self.get_parameter("cmd_timeout_s").value)
            cmd_vel_topic = str(self.get_parameter("cmd_vel_topic").value)
            driver_state_topic = str(self.get_parameter("driver_state_topic").value)
            emergency_stop_topic = str(
                self.get_parameter("emergency_stop_topic").value
            )
            clear_emergency_stop_service = str(
                self.get_parameter("clear_emergency_stop_service").value
            )
            odom_topic = str(self.get_parameter("odom_topic").value)
            self.odom_frame_id = str(self.get_parameter("odom_frame_id").value)
            self.base_frame_id = str(self.get_parameter("base_frame_id").value)
            odom_mode = str(self.get_parameter("odom_mode").value)
            publish_odom = bool(self.get_parameter("publish_odom").value)
            publish_tf = bool(self.get_parameter("publish_tf").value)
            odom_publish_hz = float(self.get_parameter("odom_publish_hz").value)
            steering_yaw_rate_radps = float(
                self.get_parameter("steering_yaw_rate_radps").value
            )

            if odom_mode != ODOM_MODE_OPEN_LOOP_COMMANDED:
                raise ValueError(
                    f"odom_mode must be {ODOM_MODE_OPEN_LOOP_COMMANDED!r}"
                )
            if odom_publish_hz <= 0:
                raise ValueError("odom_publish_hz must be greater than zero")

            self.state_pub = self.create_publisher(String, driver_state_topic, 10)
            self.create_subscription(Twist, cmd_vel_topic, self.on_cmd_vel, 10)
            self.create_subscription(
                Bool,
                emergency_stop_topic,
                self.on_emergency_stop,
                10,
            )
            self.create_service(
                Trigger,
                clear_emergency_stop_service,
                self.on_clear_emergency_stop,
            )
            self.create_timer(0.1, self.on_watchdog)

            self.worker = AsyncBleWorker(
                address=address,
                name_hint=name_hint,
                scan_seconds=scan_seconds,
            )
            self.worker.start()
            self.core = AltinoDriverCore(
                WorkerTransport(self.worker),
                wheel_base_m=wheel_base_m,
                max_linear_mps=max_linear_mps,
                cmd_timeout_s=cmd_timeout_s,
            )
            self.odom: OpenLoopOdometry | None = None
            self.odom_pub = None
            self.tf_broadcaster = None
            if publish_odom or publish_tf:
                self.odom = OpenLoopOdometry(
                    max_linear_mps=max_linear_mps,
                    steering_yaw_rate_radps=steering_yaw_rate_radps,
                    initial_time=self.core.now(),
                )
                if publish_odom:
                    self.odom_pub = self.create_publisher(Odometry, odom_topic, 10)
                if publish_tf:
                    self.tf_broadcaster = TransformBroadcaster(self)
                self.create_timer(1.0 / odom_publish_hz, self.on_odom_timer)

            self.track_future(self.worker.connect(), "connect")
            self.publish_state("connecting")

        def on_cmd_vel(self, msg: object) -> None:
            timestamp = self.core.now()
            event = self.core.handle_cmd_vel(
                float(msg.linear.x),
                float(msg.angular.z),
                now=timestamp,
            )
            self.update_odom(event, timestamp)
            self.publish_event(event)

        def on_emergency_stop(self, msg: object) -> None:
            if not bool(msg.data):
                self.publish_state("emergency_stop_ignored use_clear_service=true")
                return

            timestamp = self.core.now()
            event = self.core.emergency_stop()
            self.update_odom(event, timestamp)
            self.publish_event(event)

        def on_clear_emergency_stop(self, request: object, response: object) -> object:
            was_stopped = self.core.clear_emergency_stop()
            response.success = True
            if was_stopped:
                response.message = "emergency_stop_cleared"
                self.publish_state("emergency_stop_cleared")
            else:
                response.message = "emergency_stop_was_not_active"
                self.publish_state("emergency_stop_was_not_active")
            return response

        def on_watchdog(self) -> None:
            timestamp = self.core.now()
            event = self.core.watchdog(now=timestamp)
            if event is not None:
                self.update_odom(event, timestamp)
                self.publish_event(event)

        def on_odom_timer(self) -> None:
            if self.odom is None:
                return

            state = self.odom.advance(self.core.now())
            self.publish_odom_state(state)

        def update_odom(self, event: DriverEvent, timestamp: float) -> None:
            if self.odom is None:
                return
            self.odom.handle_event(event, timestamp=timestamp)

        def publish_event(self, event: DriverEvent) -> None:
            if isinstance(event.operation, Future):
                self.track_future(event.operation, event.message)
            self.publish_state(event.message)

        def track_future(self, future: Future[None], action: str) -> None:
            def done(done_future: Future[None]) -> None:
                try:
                    done_future.result()
                except Exception as exc:
                    self.get_logger().error(f"{action} failed: {exc}")
                    self.publish_state(f"error action={action} detail={exc}")
                else:
                    if action == "connect":
                        self.get_logger().info("connect ok")
                        self.publish_state("connected")
                    self.get_logger().debug(f"{action} ok")

            future.add_done_callback(done)

        def publish_state(self, message: str) -> None:
            self.state_pub.publish(String(data=message))

        def publish_odom_state(self, state: OdomState) -> None:
            stamp = self.get_clock().now().to_msg()
            if self.odom_pub is not None:
                self.odom_pub.publish(self.build_odom_msg(state, stamp))
            if self.tf_broadcaster is not None:
                self.tf_broadcaster.sendTransform(self.build_odom_tf(state, stamp))

        def build_odom_msg(self, state: OdomState, stamp: object) -> object:
            msg = Odometry()
            msg.header.stamp = stamp
            msg.header.frame_id = self.odom_frame_id
            msg.child_frame_id = self.base_frame_id
            msg.pose.pose.position.x = state.pose.x
            msg.pose.pose.position.y = state.pose.y
            msg.pose.pose.position.z = 0.0
            set_yaw_orientation(msg.pose.pose.orientation, state.pose.yaw)
            msg.pose.covariance = list(OPEN_LOOP_POSE_COVARIANCE)
            msg.twist.twist.linear.x = state.twist.linear_x
            msg.twist.twist.linear.y = 0.0
            msg.twist.twist.angular.z = state.twist.angular_z
            msg.twist.covariance = list(OPEN_LOOP_TWIST_COVARIANCE)
            return msg

        def build_odom_tf(self, state: OdomState, stamp: object) -> object:
            transform = TransformStamped()
            transform.header.stamp = stamp
            transform.header.frame_id = self.odom_frame_id
            transform.child_frame_id = self.base_frame_id
            transform.transform.translation.x = state.pose.x
            transform.transform.translation.y = state.pose.y
            transform.transform.translation.z = 0.0
            set_yaw_orientation(transform.transform.rotation, state.pose.yaw)
            return transform

        def close(self) -> None:
            self.worker.shutdown()

    rclpy.init(args=list(argv) if argv is not None else None)
    node: AltinoDriverNode | None = None
    previous_signal_handlers: dict[int, object] = {}

    def request_shutdown(signum: int, frame: object) -> None:
        if rclpy.ok():
            rclpy.shutdown()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_signal_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, request_shutdown)

    try:
        node = AltinoDriverNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        for signum, handler in previous_signal_handlers.items():
            signal.signal(signum, handler)
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

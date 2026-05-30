"""Optional ROS2 driver node for Altino Lite.

This module keeps ROS2 imports inside ``main`` so protocol and CLI tests can run
on machines without ROS2 installed.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Sequence
from concurrent.futures import Future

from .ble_client import AltinoBleClient
from .cmd_vel import (
    DEFAULT_MAX_LINEAR_MPS,
    DEFAULT_WHEEL_BASE_M,
)
from .driver_core import DEFAULT_CMD_TIMEOUT_S, AltinoDriverCore, DriverEvent
from .protocol import drive_frame

SHUTDOWN_OPERATION_TIMEOUT_S = 1.0
SHUTDOWN_JOIN_TIMEOUT_S = 1.0


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

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def connect(self) -> Future[None]:
        return self.submit(self.client.connect())

    def write_drive(self, left: int, right: int) -> Future[None]:
        return self.submit(self.client.write_frame(drive_frame(left, right), "cmd_vel"))

    def stop(self, reason: str) -> Future[None]:
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

    def stop(self, reason: str) -> Future[None]:
        return self.worker.stop(reason)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        import rclpy
        from geometry_msgs.msg import Twist
        from rclpy.executors import ExternalShutdownException
        from rclpy.node import Node
        from std_msgs.msg import String
    except ImportError as exc:
        print(
            "error: ROS2 Python packages are required. Source a ROS2 environment "
            "that provides rclpy, geometry_msgs, and std_msgs.",
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

            address = self.get_parameter("address").value or None
            name_hint = str(self.get_parameter("name_hint").value)
            scan_seconds = float(self.get_parameter("scan_seconds").value)

            wheel_base_m = float(self.get_parameter("wheel_base_m").value)
            max_linear_mps = float(self.get_parameter("max_linear_mps").value)
            cmd_timeout_s = float(self.get_parameter("cmd_timeout_s").value)

            self.state_pub = self.create_publisher(String, "/driver_state", 10)
            self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
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
            self.track_future(self.worker.connect(), "connect")
            self.publish_state("connecting")

        def on_cmd_vel(self, msg: object) -> None:
            event = self.core.handle_cmd_vel(
                float(msg.linear.x),
                float(msg.angular.z),
            )
            self.publish_event(event)

        def on_watchdog(self) -> None:
            event = self.core.watchdog()
            if event is not None:
                self.publish_event(event)

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

        def close(self) -> None:
            self.worker.shutdown()

    rclpy.init(args=list(argv) if argv is not None else None)
    node: AltinoDriverNode | None = None
    try:
        node = AltinoDriverNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

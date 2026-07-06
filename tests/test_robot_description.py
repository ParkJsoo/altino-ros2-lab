import pathlib
import unittest
import xml.etree.ElementTree as ET


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class RobotDescriptionTest(unittest.TestCase):
    def test_urdf_uses_base_footprint_to_base_link_chain(self) -> None:
        tree = ET.parse(REPO_ROOT / "description" / "altino_lite.urdf.xacro")
        root = tree.getroot()

        joints = {joint.attrib["name"]: joint for joint in root.findall("joint")}
        joint = joints["base_footprint_to_base_link"]

        self.assertEqual(joint.find("parent").attrib["link"], "base_footprint")
        self.assertEqual(joint.find("child").attrib["link"], "base_link")

    def test_driver_config_publishes_odom_to_base_footprint(self) -> None:
        config = (REPO_ROOT / "config" / "altino_driver.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn('odom_frame_id: "odom"', config)
        self.assertIn('base_frame_id: "base_footprint"', config)

    def test_rviz_config_includes_robot_model_display(self) -> None:
        rviz_config = (REPO_ROOT / "config" / "altino_odom_tf.rviz").read_text(
            encoding="utf-8"
        )

        self.assertIn("rviz_default_plugins/RobotModel", rviz_config)
        self.assertIn("base_footprint", rviz_config)


if __name__ == "__main__":
    unittest.main()

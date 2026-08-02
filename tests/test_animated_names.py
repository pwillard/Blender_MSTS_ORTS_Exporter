import ast
import unittest
from pathlib import Path


EXPORTER_PATH = Path(__file__).resolve().parents[1] / "io_export_mstsexporter" / "export_msts.py"


def load_helpers():
    module_ast = ast.parse(EXPORTER_PATH.read_text())
    helper_names = {"MSTSName", "IsMSTSDefinedName", "GetActionFCurves", "IsAnimated"}
    helper_nodes = [
        node for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in helper_names
    ]
    namespace = {}
    exec(compile(ast.Module(body=helper_nodes, type_ignores=[]), str(EXPORTER_PATH), "exec"), namespace)
    return namespace


class Fake:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class AnimatedNameTests(unittest.TestCase):
    def setUp(self):
        helpers = load_helpers()
        self.is_msts_defined_name = helpers["IsMSTSDefinedName"]
        self.get_action_fcurves = helpers["GetActionFCurves"]
        self.is_animated = helpers["IsAnimated"]

    def test_existing_running_gear_names_are_msts_defined(self):
        for name in ("BOGIE1", "BOGIE2", "WHEELS11", "WHEELS23", "WHEELS11.detail"):
            with self.subTest(name=name):
                self.assertTrue(self.is_msts_defined_name(name))

    def test_openrails_animation_prefix_names_are_msts_defined(self):
        supported_names = (
            "WIPER",
            "WIPER_LEFT_1",
            "DOOR_A",
            "DOOR_B_REAR",
            "DOOR_C",
            "DOOR_D",
            "DOOR_E_FRONT",
            "DOOR_F",
            "PANTOGRAPHBOTTOM1",
            "PANTOGRAPHMIDDLE1_EXTRA",
            "PANTOGRAPHTOP2",
            "PANTO3_REAR",
            "CAB_PANTO_4_LEFT",
            "MIRROR",
            "MIRROR_LEFT_1",
            "LEFTWINDOWFRONT",
            "RIGHTWINDOWFRONT_DRIVER",
            "LEFTWINDOWREAR",
            "RIGHTWINDOWREAR_2",
            "UNLOADINGPARTS",
            "UNLOADINGPARTS_1",
            "ORTSBELL",
            "ORTSITEM1CONTINUOUS",
            "ORTSITEM1TWOSTATE_A",
            "ORTSITEM2CONTINUOUS",
            "ORTSITEM2TWOSTATE_REAR",
            "ORTSBRAKECYLINDER",
            "ORTSHANDBRAKE",
            "ORTSBRAKERIGGING",
        )

        for name in supported_names:
            with self.subTest(name=name):
                self.assertTrue(self.is_msts_defined_name(name))

    def test_unsupported_names_are_not_msts_defined(self):
        unsupported_names = (
            "DOOR_G",
            "PANTO5",
            "ORTSITEM3CONTINUOUS",
            "WINDOWLEFTFRONT",
            "RANDOM_OBJECT",
        )

        for name in unsupported_names:
            with self.subTest(name=name):
                self.assertFalse(self.is_msts_defined_name(name))

    def test_legacy_action_fcurves_are_used_directly(self):
        fcurves = [Fake(data_path="location", array_index=0)]
        action = Fake(fcurves=fcurves)

        self.assertIs(self.get_action_fcurves(action), fcurves)

    def test_blender_5_action_channelbag_fcurves_match_object_slot(self):
        matching_fcurve = Fake(data_path="location", array_index=0)
        other_fcurve = Fake(data_path="rotation_euler", array_index=0)
        action = Fake(layers=[Fake(strips=[Fake(channelbags=[
            Fake(slot_handle=101, fcurves=[matching_fcurve]),
            Fake(slot_handle=202, fcurves=[other_fcurve]),
        ])])])
        node_object = Fake(animation_data=Fake(action=action, action_slot=Fake(handle=101)))

        self.assertEqual(self.get_action_fcurves(action, node_object), [matching_fcurve])
        self.assertTrue(self.is_animated(node_object))

    def test_blender_5_action_slot_handle_fallback_is_supported(self):
        matching_fcurve = Fake(data_path="location", array_index=0)
        action = Fake(layers=[Fake(strips=[Fake(channelbags=[
            Fake(slot_handle=303, fcurves=[matching_fcurve]),
        ])])])
        node_object = Fake(animation_data=Fake(action=action, action_slot_handle=303))

        self.assertEqual(self.get_action_fcurves(action, node_object), [matching_fcurve])


if __name__ == "__main__":
    unittest.main()

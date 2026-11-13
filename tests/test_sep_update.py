"""Offline regression tests for Cubi SEP two-minute native update detection."""
import ast
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/smartify_app_manager/sep_update.py"
ENTITY = ROOT / "custom_components/smartify_app_manager/update.py"
PANEL = ROOT / "custom_components/smartify_app_manager/frontend/panel.js"
INIT = ROOT / "custom_components/smartify_app_manager/__init__.py"

# Evaluate only the two standalone pure helper functions; HA is not required
# for these tests. The complete source is still parsed for syntax correctness.
_tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
_functions = [
    node for node in _tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name in ("read_installed_sep_version", "is_newer_release")
]
_ns = {"Path": Path, "json": json, "VERSION": re.compile(r"^\d+\.\d+\.\d+$")}
exec(compile(ast.Module(body=_functions, type_ignores=[]), str(SOURCE), "exec"), _ns)
read_installed = _ns["read_installed_sep_version"]
is_newer = _ns["is_newer_release"]


class SEPUpdatePollingTests(unittest.TestCase):
    def test_installed_version_is_from_manifest_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            self.assertIsNone(read_installed(str(path)))
            path.write_text(json.dumps({
                "domain": "smartify_energy", "version": "0.3.87"
            }), encoding="utf-8")
            self.assertEqual(read_installed(str(path)), "0.3.87")
            path.write_text(json.dumps({
                "domain": "another_integration", "version": "0.3.87"
            }), encoding="utf-8")
            self.assertIsNone(read_installed(str(path)))
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(read_installed(str(path)))

    def test_updates_do_not_include_downgrades(self):
        self.assertTrue(is_newer("0.3.87", "0.3.88"))
        self.assertTrue(is_newer("0.3.87", "0.4.0"))
        self.assertFalse(is_newer("0.3.88", "0.3.87"))
        self.assertFalse(is_newer("0.3.87", "0.3.87"))
        self.assertFalse(is_newer(None, "0.3.88"))
        self.assertFalse(is_newer("invalid", "0.3.88"))

    def test_native_update_and_periodic_coordinator_wiring(self):
        sep = SOURCE.read_text(encoding="utf-8")
        entity = ENTITY.read_text(encoding="utf-8")
        init = INIT.read_text(encoding="utf-8")
        self.assertIn("UPDATE_INTERVAL = timedelta(minutes=2)", sep)
        self.assertIn("update_interval=UPDATE_INTERVAL", sep)
        self.assertIn("class CubiSEPUpdateEntity(", entity)
        self.assertIn("UpdateEntity):", entity)
        self.assertIn("_attr_supported_features = UpdateEntityFeature.INSTALL", entity)
        self.assertIn("async_install", entity)
        self.assertIn("class CubiAppUpdateEntity(", entity)
        self.assertIn('async_forward_entry_setups(entry, ["update"])', init)
        self.assertIn('async_unload_platforms(entry, ["update"])', init)

    def test_brand_images_are_original_repo_sources(self):
        panel = PANEL.read_text(encoding="utf-8")
        for path in (
            "smartify-energy-pro/main/custom_components/smartify_energy/brand/icon.png",
            "smartify-flow-card/main/custom_components/smartify_flow_card/brand/icon.png",
            "smartify-weather-card/main/images/icon.png",
            "smartify-person-detection/main/images/icon.png",
            "smartify-sip-manager/main/images/icon.png",
            "smartify-heating/main/custom_components/smartify_heating/brand/icon.png",
            "smartify-raffstore/main/images/icon.png",
            "smartify-tailnet-viewer/main/images/icon.png",
            "smartify-tabbar/main/images/icon.png",
        ):
            with self.subTest(path=path):
                self.assertIn(path, panel)
        self.assertIn("img.addEventListener('error'", panel)
        self.assertIn("Cubi-Paketserver", panel)
        self.assertIn("}, 120000)", panel)


if __name__ == "__main__":
    unittest.main()

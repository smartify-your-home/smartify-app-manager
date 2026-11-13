"""Offline security and immutability tests for Kubi SEP package transport."""
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
import types
import unittest
from zipfile import ZipFile

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/smartify_app_manager/kubi_source.py"
# This standalone test runner does not import Home Assistant.
ha = types.ModuleType("homeassistant")
helpers = types.ModuleType("homeassistant.helpers")
aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = lambda hass: None
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_client)
spec = importlib.util.spec_from_file_location("kubi_source", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

META = {
    "module": "smartify-energy-pro", "version": "0.3.87", "tag": "0.3.87",
    "archive": "smartify-energy-pro-0.3.87.zip",
    "release_notes": "smartify-energy-pro-0.3.87-release-notes.md",
    "verified_published_release": True,
    "sha256": "a" * 64, "source_commit": "b" * 40,
}


def archive(paths=None, version="0.3.87"):
    default = {
        "INSTALLATION.txt": "test",
        "custom_components/smartify_energy/__init__.py": "# init",
        "custom_components/smartify_energy/manifest.json": json.dumps({
            "domain": "smartify_energy", "version": version
        }),
    }
    if paths:
        default.update(paths)
    buf = BytesIO()
    with ZipFile(buf, "w") as z:
        for name, body in default.items():
            z.writestr(name, body)
    return buf.getvalue()


class KubiSourceTests(unittest.TestCase):
    def test_private_lan_url(self):
        self.assertEqual(
            mod.validate_server_url(" http://192.168.2.122:8765/ "),
            "http://192.168.2.122:8765",
        )
        self.assertEqual(mod.validate_server_url(""), "")
        self.assertEqual(
            mod.validate_server_url(" https://smartify-packages.tail8ff129.ts.net/ "),
            "https://smartify-packages.tail8ff129.ts.net",
        )
        self.assertEqual(
            mod.validate_server_url("https://smartify-packages.tail8ff129.ts.net:443"),
            "https://smartify-packages.tail8ff129.ts.net",
        )
        for bad in (
            "http://127.0.0.1", "http://1.1.1.1:8765",
            "http://192.168.2.122:8765/a", "http://192.168.2.122:8765/?a=1",
            "http://localhost:8765", "http://user:pass@192.168.2.122",
            "file:///etc/passwd", "https://192.168.2.122",
            "https://100.81.101.76",
            "https://github.com", "https://evil.example",
            "http://smartify-packages.tail8ff129.ts.net",
            "https://smartify-packages.tail8ff129.ts.net:444",
            "https://smartify-packages.tail8ff129.ts.net/sep/latest.json",
            "https://user@smartify-packages.tail8ff129.ts.net",
        ):
            with self.subTest(bad=bad), self.assertRaises(mod.KubiError):
                mod.validate_server_url(bad)

    def test_metadata_contract(self):
        self.assertEqual(mod.validate_metadata(META)["version"], "0.3.87")
        for changed in (
            {"version": "0.3.87/../../etc"}, {"archive": "malicious.zip"},
            {"module": "other"}, {"verified_published_release": False},
            {"sha256": "0000"}, {"source_commit": "1234"},
        ):
            with self.subTest(changed=changed), self.assertRaises(mod.KubiError):
                mod.validate_metadata({**META, **changed})

    def test_zip_validation(self):
        mod._validate_zip(archive(), "0.3.87")
        with self.assertRaises(mod.KubiError):
            mod._validate_zip(archive(version="0.3.86"), "0.3.87")
        with self.assertRaises(mod.KubiError):
            mod._validate_zip(archive({"../evil.txt": "BAD"}), "0.3.87")
        with self.assertRaises(mod.KubiError):
            mod._validate_zip(archive({"custom_components/evil.py": "BAD"}), "0.3.87")

    def test_storage_immutable(self):
        import tempfile
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as cfg:
            data = archive()
            digest = sha256(data).hexdigest()
            path = mod._store_verified(
                cfg, "smartify-energy-pro-0.3.87.zip", data, digest
            )
            self.assertTrue(Path(path).is_file())
            self.assertEqual(
                path, mod._store_verified(
                    cfg, "smartify-energy-pro-0.3.87.zip", data, digest
                )
            )
            with self.assertRaises(mod.KubiError):
                mod._store_verified(
                    cfg, "smartify-energy-pro-0.3.87.zip", b"changed", "f" * 64
                )


if __name__ == "__main__":
    unittest.main()

"""Offline tests for the central Cubi deny-by-default release policy."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cubi_package_policy', ROOT / 'cubi/package_policy.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
SAMPLE = ROOT / 'cubi/package-policy.example.json'


class CubiPackagePolicyTests(unittest.TestCase):
    def setUp(self):
        self.sample = mod.load_policy(SAMPLE)

    def test_sep_only_enabled(self):
        self.assertEqual(mod.approved_repositories(self.sample, 'sync'), ['smartify-energy-pro'])
        self.assertEqual(mod.approved_repositories(self.sample, 'publish'), ['smartify-energy-pro'])
        self.assertFalse(mod.is_allowed(self.sample, 'smartify-flow-card', 'sync'))
        self.assertFalse(mod.is_allowed(self.sample, 'smartify-themes', 'publish'))
        self.assertFalse(mod.is_allowed(self.sample, '../evil', 'sync'))

    def test_disabled_or_internal_apps_not_published(self):
        policy = json.loads(SAMPLE.read_text())
        policy['apps']['smartify-internal'] = {'sync': False, 'publish': False, 'release_dir': 'internal'}
        policy['apps']['smartify-devtools'] = {'sync': True, 'publish': False, 'release_dir': 'devtools'}
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'policy.json'
            p.write_text(json.dumps(policy))
            loaded = mod.load_policy(p)
            self.assertFalse(mod.is_allowed(loaded, 'smartify-internal', 'sync'))
            self.assertTrue(mod.is_allowed(loaded, 'smartify-devtools', 'sync'))
            self.assertFalse(mod.is_allowed(loaded, 'smartify-devtools', 'publish'))

    def test_reject_invalid_and_missing_configuration(self):
        samples = [
            '{"schema_version":1,"schema_version":1}',
            json.dumps({**self.sample, 'default': 'allow'}),
            json.dumps({**self.sample, 'github_owner': 'someone-else'}),
            json.dumps({**self.sample, 'apps': {'smartify-a': {'sync': False, 'publish': True, 'release_dir': 'a'}}}),
            json.dumps({**self.sample, 'apps': {'smartify-a': {'sync': 'true', 'publish': False, 'release_dir': 'a'}}}),
            json.dumps({**self.sample, 'apps': {'smartify-a': {'sync': True, 'publish': True, 'release_dir': '../a'}}}),
            json.dumps({**self.sample, 'apps': {'smartify-a': {'sync': True, 'publish': True, 'release_dir': 'same'}, 'smartify-b': {'sync': True, 'publish': True, 'release_dir': 'same'}}}),
        ]
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'p.json'
            with self.assertRaises(mod.PolicyError):
                mod.load_policy(p)
            for item in samples:
                with self.subTest(item=item):
                    p.write_text(item)
                    with self.assertRaises(mod.PolicyError):
                        mod.load_policy(p)

    def test_public_directory_audit_flags_leftovers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'sep').mkdir()
            self.assertEqual(mod.unexpected_public_directories(self.sample, root), [])
            (root / 'internal-app.zip').write_bytes(b'test')
            self.assertEqual(mod.unexpected_public_directories(self.sample, root), ['internal-app.zip'])
            (root / 'sep').rmdir()
            (root / 'sep').symlink_to(root / 'internal-app.zip')
            self.assertEqual(mod.unexpected_public_directories(self.sample, root), ['internal-app.zip', 'sep'])

    def test_cli_denies_unlisted_repositories(self):
        self.assertEqual(mod.main(['--policy', str(SAMPLE), 'check', 'sync', 'smartify-energy-pro']), 0)
        self.assertEqual(mod.main(['--policy', str(SAMPLE), 'check', 'sync', 'smartify-row-card']), 1)


if __name__ == '__main__':
    unittest.main()

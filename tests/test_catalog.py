"""Dependency-free catalog invariants."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'custom_components' / 'smartify_app_manager'

class CatalogTests(unittest.TestCase):
    def test_manifest(self):
        d=json.loads((MODULE/'manifest.json').read_text())
        self.assertEqual(d['domain'],'smartify_app_manager')
        self.assertEqual(d['version'],'0.2.0')
    def test_marketplace_manifest(self):
        d=json.loads((ROOT/'hacs.json').read_text())
        self.assertEqual(d['name'], 'Smartify App Manager')
        self.assertNotIn('content_in_root', d)
        self.assertTrue((MODULE/'manifest.json').exists())

    def test_sync_uses_interval_and_owner_filter(self):
        src=(MODULE/'catalog_sync.py').read_text()
        compile(src, str(MODULE/'catalog_sync.py'), 'exec')
        self.assertIn('REFRESH_SECONDS = 6 * 60 * 60', src)
        self.assertIn('MANUAL_MIN_SECONDS = 10 * 60', src)
        self.assertIn('GITHUB_OWNER', src)

    def test_catalog_unique_and_safe(self):
        tree=ast.parse((MODULE/'const.py').read_text())
        item=next(x for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='APPS' for t in x.targets))
        apps=ast.literal_eval(item.value)
        self.assertEqual(len(apps),12)
        self.assertEqual(len({a[0] for a in apps}),len(apps))
        self.assertEqual(len({a[2] for a in apps}),len(apps))
        self.assertTrue(all(len(a)==5 and '/' not in a[2] for a in apps))
    def test_ha_files_are_syntax_valid(self):
        for path in MODULE.glob('*.py'):
            compile(path.read_text(),str(path),'exec')

if __name__=='__main__': unittest.main()

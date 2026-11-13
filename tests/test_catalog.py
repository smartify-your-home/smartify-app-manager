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
        self.assertEqual(d['version'],'0.1.0')
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

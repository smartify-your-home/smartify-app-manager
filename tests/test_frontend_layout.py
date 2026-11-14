"""Static regressions for the compact Smartify app catalog layout."""
from pathlib import Path
import unittest

PANEL = (Path(__file__).resolve().parents[1]
         / "custom_components/smartify_app_manager/frontend/panel.js")


class AppListLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PANEL.read_text(encoding="utf-8")

    def test_catalog_uses_compact_single_column_list(self):
        self.assertIn('class="apps-list" role="list"', self.source)
        self.assertIn('class="app-row" role="listitem"', self.source)
        self.assertIn("grid-template-columns:34px minmax(0,1fr) auto", self.source)
        self.assertNotIn('class="grid"', self.source)
        self.assertNotIn('class="app"', self.source)

    def test_controls_remain_accessible(self):
        for required in (
            'class="app-actions"',
            "escape(app.url)",
            "escape(app.release_url)",
            "data-id",
            "data-locked",
            'role="listitem"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_icon_has_immediate_fallback_and_cached_load_handler(self):
        source = self.source
        self.assertIn("data-smartify-src", source)
        self.assertIn("img.addEventListener('load'", source)
        self.assertIn("img.addEventListener('error'", source)
        self.assertLess(source.index("img.addEventListener('load'"),
                        source.index("img.src = img.dataset.smartifySrc"))
        self.assertLess(source.index("img.addEventListener('error'"),
                        source.index("img.src = img.dataset.smartifySrc"))
        self.assertIn("this._cubiCatalog.stale", source)

    def test_mobile_actions_wrap_below_details(self):
        self.assertIn("@media (max-width:720px)", self.source)
        self.assertIn(".app-actions{grid-column:2;justify-content:flex-start}", self.source)


if __name__ == "__main__":
    unittest.main()

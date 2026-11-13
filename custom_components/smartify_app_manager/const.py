"""Smartify catalog metadata; each item stays in its own repository."""
DOMAIN = "smartify_app_manager"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.settings"
PANEL_PATH = "smartify"
GITHUB_OWNER = "smartify-your-home"

# Installation is deliberately delegated to HA/HACS. No arbitrary code downloading.
APPS = (
    ("energy-pro", "Smartify Energy Pro", "smartify-energy-pro", "integration", "zap"),
    ("flow-card", "Smartify Flow Card", "smartify-flow-card", "dashboard", "network"),
    ("weather-card", "Smartify Weather Card", "smartify-weather-card", "dashboard", "cloud-sun"),
    ("person-detection", "Smartify Person Detection", "smartify-person-detection", "integration", "scan-face"),
    ("floorplan3d", "Smartify Floorplan 3D", "smartify-floorplan3D", "dashboard", "house"),
    ("sip-manager", "Smartify SIP Manager", "smartify-sip-manager", "integration", "phone"),
    ("themes", "Smartify Themes", "smartify-themes", "theme", "palette"),
    ("heating", "Smartify Heating", "smartify-heating", "integration", "thermometer"),
    ("raffstore", "Smartify Raffstore", "smartify-raffstore", "dashboard", "blinds"),
    ("tailnet-viewer", "Smartify Tailnet Viewer", "smartify-tailnet-viewer", "integration", "network"),
    ("tabbar", "Smartify Tabbar", "smartify-tabbar", "dashboard", "layout"),
    ("row-card", "Smartify Row Card", "smartify-row-card", "dashboard", "rows"),
)

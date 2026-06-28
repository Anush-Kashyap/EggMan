from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "EggMan"
IS_FROZEN = bool(getattr(sys, "frozen", False))
PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(sys.executable).resolve().parent if IS_FROZEN else PROJECT_ROOT
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))

if IS_FROZEN:
    _app_data_base = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    USER_DATA_ROOT = Path(os.getenv("EGGMAN_DATA_DIR", _app_data_base / APP_NAME))
else:
    USER_DATA_ROOT = PROJECT_ROOT

BASE_DIR = str(PROJECT_ROOT)
ASSETS_DIR = RESOURCE_ROOT / "assets"
APP_ICON_PATH = ASSETS_DIR / "eggman.ico"


def _path(*parts) -> str:
    return str(USER_DATA_ROOT.joinpath(*parts))


def resource_path(*parts) -> str:
    return str(RESOURCE_ROOT.joinpath(*parts))


def external_path(*parts) -> str:
    return str(APP_ROOT.joinpath(*parts))


EXPORTS_DIR = _path("data", "exports")
SCREENSHOTS_DIR = _path("data", "screenshots")

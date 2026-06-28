import json
import os

from core.paths import _path


class SettingsManager:
    _FILE = _path("eggman_settings.json")

    _DEFAULTS = {
        "always_on_top": True,
        "win_x": None,
        "win_y": None,
        "win_w": 270,
        "win_h": 500,
        "theme": "light",
    }

    def __init__(self):
        self._data: dict = dict(self._DEFAULTS)
        self._load()

    def _load(self):
        if os.path.exists(self._FILE):
            try:
                with open(self._FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key in self._DEFAULTS:
                    if key in saved:
                        self._data[key] = saved[key]
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        try:
            with open(self._FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def get(self, key: str):
        return self._data.get(key, self._DEFAULTS.get(key))

    def set(self, key: str, value):
        self._data[key] = value

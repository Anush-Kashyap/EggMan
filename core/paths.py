import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path(*parts) -> str:
    return os.path.join(BASE_DIR, *parts)


EXPORTS_DIR = _path("data", "exports")
SCREENSHOTS_DIR = _path("data", "screenshots")

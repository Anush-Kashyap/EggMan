# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from faster_whisper.utils import get_assets_path
import openwakeword
from pathlib import Path


block_cipher = None

hiddenimports = [
    "tkinter",
    "_tkinter",
    "openwakeword",
    "scipy",
    "sklearn",
    *collect_submodules("backend"),
    *collect_submodules("core"),
    *collect_submodules("ui"),
    *collect_submodules("app"),
]

datas = [
    ("assets", "assets"),
    ("data/config.json", "data"),
    (get_assets_path(), "faster_whisper/assets"),
    (str(Path(openwakeword.__file__).parent / "resources"), "openwakeword/resources"),
    (str(Path(openwakeword.__file__).parent / "resources"), "_internal/openwakeword/resources"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "chromadb",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EggMan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/eggman.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EggMan",
)

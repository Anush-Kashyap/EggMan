# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from faster_whisper.utils import get_assets_path


block_cipher = None

hiddenimports = [
    "tkinter",
    "_tkinter",
    "openwakeword",
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
    "onnxruntime.capi.onnxruntime_pybind11_state",
    "scipy",
    "sklearn",
    "numpy",
    *collect_submodules("openwakeword"),
    *collect_submodules("backend"),
    *collect_submodules("core"),
    *collect_submodules("ui"),
    *collect_submodules("app"),
]

datas = [
    ("assets", "assets"),
    ("data/config.json", "data"),
    (get_assets_path(), "faster_whisper/assets"),
    *collect_data_files("openwakeword", includes=["resources/**/*"]),
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
    icon="assets/eggman.ico",
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

# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Pipit Clone (Windows GUI).

Build from the repository root (prefer the project venv — see build_windows_exe.ps1):
  python -m PyInstaller pipit_clone.spec --clean --noconfirm

Output: dist/PipitClone/PipitClone.exe (one-folder bundle; recommended for ONNX/Qt/DirectML).

Do not use collect_all(PySide6): it pulls every Qt module (3D, QML, …) and makes the build huge.
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

block_cipher = None

spec_root = os.path.dirname(os.path.abspath(SPEC))

datas: list = []
binaries: list = []
hiddenimports = [
    "pipit_clone",
    "pipit_clone.ui_main",
    "pipit_clone.audio_utils",
    "pipit_clone.config",
    "pipit_clone.onnx_asr_engine",
    "pipit_clone.parakeet_windows_installer",
    "pipit_clone.stt_client",
    "pipit_clone.win32_paste",
    "sounddevice",
    "_sounddevice_data",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "certifi",
    "onnx_asr",
    "onnxruntime",
    "py7zr",
]

try:
    binaries += collect_dynamic_libs("onnxruntime")
except Exception:
    pass

try:
    datas += collect_data_files("certifi")
except Exception:
    pass

# onnx_asr reads __version__ via importlib.metadata.version("onnx-asr"); frozen apps need dist-info.
try:
    datas += copy_metadata("onnx-asr")
except Exception:
    pass

# Bundled preprocessor ONNX models (e.g. nemo128.onnx) live under onnx_asr/preprocessors/data/.
try:
    datas += collect_data_files("onnx_asr")
except Exception:
    pass

a = Analysis(
    [os.path.join(spec_root, "pipit_clone", "__main__.py")],
    pathex=[spec_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="PipitClone",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PipitClone",
)

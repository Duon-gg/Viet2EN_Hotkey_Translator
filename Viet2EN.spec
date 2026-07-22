# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import uiautomation
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)


datas = [("assets", "assets")]
binaries = []
hiddenimports = [
    "keyboard",
    "pyperclip",
    "pystray._win32",
    "win32clipboard",
    "websockets.sync.server",
]

# Argos and UI Automation are imported lazily. Collect their code/data without
# recursively bundling their development suites. RapidOCR needs its bundled ONNX
# models, so collect_all remains appropriate for that small package.
datas += collect_data_files("argostranslate")
datas += collect_data_files("uiautomation")
hiddenimports += collect_submodules("argostranslate")
hiddenimports += collect_submodules("uiautomation")

rapid_datas, rapid_binaries, rapid_hiddenimports = collect_all("rapidocr_onnxruntime")
datas += rapid_datas
binaries += rapid_binaries
hiddenimports += rapid_hiddenimports

uia_bin = Path(uiautomation.__file__).resolve().parent / "bin"
for dll_name in ("UIAutomationClient_VC140_X64.dll", "UIAutomationClient_VC140_X86.dll"):
    binaries.append((str(uia_bin / dll_name), "uiautomation/bin"))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "comtypes.test",
        "mypy",
        "mypyc",
        "onnxruntime.backend",
        "onnxruntime.datasets",
        "onnxruntime.quantization",
        "onnxruntime.tools",
        "onnxruntime.transformers",
        "pytest",
        "spacy",
        "spacy.tests",
        "stanza",
        "torch",
        "torch.testing",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Viet2EN",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon="assets\\icon-v2.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Viet2EN",
)

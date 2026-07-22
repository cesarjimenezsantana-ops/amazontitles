from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(SPECPATH).resolve().parent
APP_NAME = "Focus Amazon Tools"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")

data_files = [
    (str(ROOT_DIR / "templates"), "templates"),
    (str(ROOT_DIR / "static"), "static"),
    (str(ROOT_DIR / "packaging" / "assets"), "packaging/assets"),
]
for reference_path in sorted(ROOT_DIR.glob("*.xlsx")):
    data_files.append((str(reference_path), "."))

if sys.platform == "darwin":
    icon_path = ROOT_DIR / "packaging" / "assets" / "app-icon.icns"
    excluded_modules = [
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "clr",
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "webview.platforms.winforms",
    ]
else:
    icon_path = ROOT_DIR / "packaging" / "assets" / "app-icon.ico"
    excluded_modules = [
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.qt",
    ]

analysis = Analysis(
    [str(ROOT_DIR / "desktop_app.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=data_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=1,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
)

application_files = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    application = BUNDLE(
        application_files,
        name=f"{APP_NAME}.app",
        icon=str(icon_path),
        bundle_identifier="com.focusamazontools.desktop",
        version=APP_VERSION,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "LSApplicationCategoryType": "public.app-category.business",
            "NSHighResolutionCapable": True,
        },
    )

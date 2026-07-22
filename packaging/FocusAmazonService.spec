from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(SPECPATH).resolve().parent

data_files = [
    (str(ROOT_DIR / "templates"), "templates"),
    (str(ROOT_DIR / "static"), "static"),
    (str(ROOT_DIR / "packaging" / "assets"), "packaging/assets"),
]
for reference_path in sorted(ROOT_DIR.glob("*.xlsx")):
    data_files.append((str(reference_path), "."))

analysis = Analysis(
    [str(ROOT_DIR / "electron_service.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=data_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["webview", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
    optimize=1,
)
python_archive = PYZ(analysis.pure)
executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="FocusAmazonService",
    console=True,
    disable_windowed_traceback=False,
)
application_files = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="FocusAmazonService",
)

# PyInstaller spec for the PageVault desktop application.
#
# Build (one-folder):  pyinstaller pagevault.spec --noconfirm
# Output:              dist/PageVault/PageVault.exe  (+ supporting files)
#
# One-folder rather than one-file: it starts faster and triggers far fewer
# antivirus false positives, which matters for a publicly downloaded release.

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

APP_NAME = "PageVault"
ROOT = Path(SPECPATH)  # noqa: F821 — SPECPATH is injected by PyInstaller

# Conda Pythons keep dependent DLLs (sqlite3.dll, libssl, ffi, ...) in
# <base_prefix>/Library/bin, which PyInstaller does not search by default, so
# those libraries silently fail to bundle. Add it to PATH for the dependency
# scan. No-op on standard python.org builds (e.g. the CI runner).
_conda_bin = Path(sys.base_prefix) / "Library" / "bin"
if _conda_bin.is_dir():
    os.environ["PATH"] = str(_conda_bin) + os.pathsep + os.environ.get("PATH", "")

# Bundled read-only resources. resource_dir() resolves these under sys._MEIPASS
# at runtime (see config.py).
datas = [
    ("templates", "templates"),
    ("static", "static"),
]
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = collect_submodules("waitress")

# pywebview pulls in its platform backend (WebView2 via pythonnet on Windows);
# collect everything it needs so the frozen app can open a native window.
for package in ("webview", "clr_loader", "pythonnet"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # noqa: BLE001 — a missing optional backend must not break the build
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(  # noqa: F821
    ["desktop.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app: no console window
    disable_windowed_traceback=False,
    icon=str(ROOT / "static" / "icon.ico"),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

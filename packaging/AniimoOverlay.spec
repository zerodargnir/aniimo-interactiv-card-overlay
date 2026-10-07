# PyInstaller spec: single AniimoOverlay.exe (build on Windows).
#   pyinstaller --noconfirm --clean packaging/AniimoOverlay.spec
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is defined by PyInstaller
SRC = ROOT / "src"
RESOURCES = SRC / "aniimo_overlay" / "resources"

hiddenimports = (
    collect_submodules("aniimo_overlay")
    + collect_submodules("pynput")  # backends (_win32, _xorg...) are imported dynamically
)

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(RESOURCES), "aniimo_overlay/resources")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "_tkinter",
        "unittest",
        "pydoc",
        "pytest",
        "matplotlib",
        "IPython",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtBluetooth",
        "PySide6.QtDesigner",
        "PySide6.QtSql",
        "PySide6.QtTest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Shown by the bootloader while the onefile archive unpacks (before Python starts).
# Needs Tcl/Tk on the build machine (always there with the python.org Windows installer).
try:
    import tkinter  # noqa: F401

    splash = Splash(
        str(ROOT / "packaging" / "splash.png"),
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        always_on_top=False,
    )
    splash_parts = [splash, splash.binaries]
except ImportError:
    print("WARNING: tkinter missing, building without splash screen")
    splash_parts = []

exe = EXE(
    pyz,
    a.scripts,
    *splash_parts,
    a.binaries,
    a.datas,
    [],
    name="AniimoOverlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # no packer: fewer antivirus false positives
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=str(RESOURCES / "app.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
)

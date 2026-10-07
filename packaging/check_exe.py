"""Check that the onefile exe contains the QtWebEngine runtime files.

python packaging/check_exe.py dist/AniimoOverlay.exe
"""

from __future__ import annotations

import sys

from PyInstaller.archive.readers import CArchiveReader

REQUIRED = [
    "QtWebEngineProcess",
    "icudtl.dat",
    "qtwebengine_resources.pak",
    "qtwebengine_locales",
    "aniimo_overlay/resources/app.ico",
    "aniimo_overlay/resources/style.qss",
]


def main() -> int:
    archive = CArchiveReader(sys.argv[1])
    names = [name.replace("\\", "/") for name in archive.toc]
    missing = [item for item in REQUIRED if not any(item in name for name in names)]
    for item in REQUIRED:
        print(("MISSING  " if item in missing else "ok       ") + item)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

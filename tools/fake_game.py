"""Show an image full screen to simulate the game during development.

    python tools/fake_game.py tests/fixtures/synthetic/ne_01.png

Window title is "Aniimo (fake)" so it is found by the game window lookup on Windows.
Escape or Q closes it.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel


class FakeGame(QLabel):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.setWindowTitle("Aniimo (fake)")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: black;")
        self._pixmap = QPixmap(path)
        if self._pixmap.isNull():
            raise SystemExit(f"Cannot read image: {path}")

    def resizeEvent(self, event) -> None:
        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    app = QApplication(sys.argv[:1])
    window = FakeGame(sys.argv[1])
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

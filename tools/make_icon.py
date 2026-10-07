"""Draw the application icon (our own artwork) and the exe splash image.

    QT_QPA_PLATFORM=offscreen python tools/make_icon.py

Writes src/aniimo_overlay/resources/app.png, app.ico and packaging/splash.png.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src" / "aniimo_overlay" / "resources"
BG = QColor("#16171b")
RING = QColor("#3a3d47")
ORANGE = QColor("#ff8c1a")
BLUE = QColor("#3d8bff")
WHITE = QColor("#f2f3f5")


def draw_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256.0
    path = QPainterPath()
    path.addRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 52 * s, 52 * s)
    p.fillPath(path, BG)

    # compass ring and ticks
    p.setPen(QPen(RING, max(1.0, 10 * s)))
    p.drawEllipse(QPointF(128 * s, 128 * s), 88 * s, 88 * s)
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        p.drawLine(
            QPointF((128 + dx * 70) * s, (128 + dy * 70) * s),
            QPointF((128 + dx * 100) * s, (128 + dy * 100) * s),
        )

    orange = QPointF(92 * s, 164 * s)
    blue = QPointF(168 * s, 88 * s)
    # arrow orange -> blue
    p.setPen(QPen(WHITE, max(1.5, 12 * s), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(orange, QPointF(146 * s, 110 * s))
    head = QPainterPath()
    head.moveTo(blue + QPointF(-4 * s, 4 * s))
    head.lineTo(QPointF(128 * s, 104 * s))
    head.lineTo(QPointF(152 * s, 128 * s))
    head.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.fillPath(head, WHITE)

    p.setBrush(ORANGE)
    p.drawEllipse(orange, 24 * s, 24 * s)
    p.setBrush(BLUE)
    p.drawEllipse(blue + QPointF(8 * s, -8 * s), 24 * s, 24 * s)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def write_ico(path: Path, sizes: list[int]) -> None:
    """ICO container with PNG-compressed entries (supported since Windows Vista)."""
    images = [png_bytes(draw_icon(size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for size, data in zip(sizes, images, strict=True):
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + entries + b"".join(images))


def draw_splash() -> QImage:
    img = QImage(420, 200, QImage.Format.Format_RGB32)
    img.fill(BG)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.drawImage(QRectF(28, 52, 96, 96), draw_icon(192))
    p.setPen(WHITE)
    font = QFont()
    font.setPointSize(18)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(144, 62, 260, 40), Qt.AlignmentFlag.AlignVCenter, "Aniimo Overlay")
    font.setPointSize(10)
    font.setBold(False)
    p.setFont(font)
    p.setPen(QColor("#8b8e99"))
    p.drawText(QRectF(144, 104, 260, 30), Qt.AlignmentFlag.AlignVCenter, "Chargement…")
    p.end()
    return img


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841 - needed for fonts
    RESOURCES.mkdir(parents=True, exist_ok=True)
    draw_icon(256).save(str(RESOURCES / "app.png"))
    write_ico(RESOURCES / "app.ico", [16, 24, 32, 48, 64, 128, 256])
    draw_splash().save(str(ROOT / "packaging" / "splash.png"))
    print("Icon and splash written")


if __name__ == "__main__":
    main()

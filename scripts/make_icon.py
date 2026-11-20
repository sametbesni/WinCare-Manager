"""assets/app.ico dosyasını Qt ile çizerek üretir.

Kullanım (proje klasöründe):  python scripts/make_icon.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#3b82f6"))
    gradient.setColorAt(1, QColor("#1d4ed8"))
    p.setBrush(gradient)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 52 * s, 52 * s)

    # Monitör
    pen = QPen(QColor("#ffffff"), 16 * s)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(46 * s, 62 * s, 164 * s, 108 * s), 14 * s, 14 * s)
    p.drawLine(128 * s, 172 * s, 128 * s, 200 * s)
    p.drawLine(92 * s, 202 * s, 164 * s, 202 * s)

    # Sağlık işareti (onay)
    pen.setColor(QColor("#7ce0bf"))
    pen.setWidthF(18 * s)
    p.setPen(pen)
    p.drawPolyline([QRectF(84 * s, 116 * s, 0, 0).topLeft(), QRectF(114 * s, 144 * s, 0, 0).topLeft(),
                    QRectF(170 * s, 92 * s, 0, 0).topLeft()])
    p.end()
    return image


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def build_ico(sizes: tuple[int, ...] = ICON_SIZES) -> bytes:
    """Çok boyutlu ICO (PNG sıkıştırmalı girdiler, Windows Vista ve sonrası).

    Her boyut ayrı çizilir; böylece masaüstü, görev çubuğu ve gezgin küçük
    boyutlarda bulanık ölçeklenmiş bir görüntü göstermez.
    """
    images = [png_bytes(draw(size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for size, data in zip(sizes, images):
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(images)


def main() -> int:
    _app = QGuiApplication(sys.argv)
    target = ROOT / "assets" / "app.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_ico())
    draw(256).save(str(ROOT / "assets" / "app.png"), "PNG")
    print(f"Oluşturuldu: {target} ({', '.join(map(str, ICON_SIZES))} px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

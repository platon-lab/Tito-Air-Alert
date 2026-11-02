"""Генерує значок шахеда (дельтакрило) у PNG без зовнішніх бібліотек.
Замінити можна будь-яким своїм PNG: назви icon_red.png / icon_yellow.png."""
import os
import struct
import zlib

import storage

COLORS = {"red": (198, 40, 40), "yellow": (249, 168, 37)}


def _inside(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def make_drone_png(path, rgb, size=64):
    # Контур дельтакрила: носик нагорі, крила внизу, виїмка ззаду.
    poly = [(32, 3), (61, 59), (32, 45), (3, 59)]
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # фільтр рядка
        for x in range(size):
            if _inside(x + 0.5, y + 0.5, poly):
                raw += bytes((rgb[0], rgb[1], rgb[2], 255))
            else:
                raw += b"\x00\x00\x00\x00"
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def ensure_icons():
    paths = {}
    for name, rgb in COLORS.items():
        path = storage.icon_path(name)
        if not os.path.exists(path):
            make_drone_png(path, rgb)
        paths[name] = path
    return paths

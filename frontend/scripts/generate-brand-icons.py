"""Render the TargetMind favicon / PWA icon set from the brand mark.

Run from ``frontend/``::

    python3 scripts/generate-brand-icons.py

Outputs into ``public/``. The mark mirrors ``src/assets/branding/targetmind-logo.svg``
("helix roundtable"): a DNA double helix closed into a ring, five expert seats
in its eyes and the coral target at the centre, on a white tile.
"""

from __future__ import annotations

import io
import math
import os
import struct

from PIL import Image, ImageDraw

TILE = (255, 255, 255, 255)  # white tile
TILE_EDGE = (226, 233, 240, 255)  # --color-tm-line, keeps the tile visible on white
STRAND_A = (27, 77, 107, 255)  # --color-tm-navy, matches targetmind-logo.svg
STRAND_B = (14, 124, 155, 255)  # --color-tm-teal
SEATS = [
    (27, 77, 107, 255),
    (14, 124, 155, 255),
    (79, 169, 201, 255),
    (58, 92, 204, 255),
    (108, 99, 217, 255),
]
TARGET = (240, 90, 60, 255)  # coral: the discovered target

SS = 8  # supersample factor
PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")

# Mark geometry in 32-unit SVG space (same numbers as the SVG).
RING_R, AMP, TWISTS = 11.5, 2.75, 5


def _ellipse(draw, cx, cy, r, **kw):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), **kw)


def _strand(sign: int, scale: float, inset: float, pad: float) -> list[tuple[float, float]]:
    pts = []
    for i in range(360):
        t = math.radians(i)
        r = (RING_R + sign * AMP * math.sin(TWISTS * t)) * scale
        pts.append((pad + inset + r * math.cos(t), pad + inset + r * math.sin(t)))
    return pts


def render(size: int, background: bool = True) -> Image.Image:
    """Draw the mark at ``size`` px, supersampled then downscaled."""
    s = size * SS
    tiny = size <= 32  # below this, use a round tile and heavier strokes

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if background:
        radius = s * (0.5 if tiny else 0.22)
        edge = max(1, round(s / (24 if tiny else 96)))
        draw.rounded_rectangle(
            (0, 0, s - 1, s - 1), radius=radius, fill=TILE, outline=TILE_EDGE, width=edge
        )

    # The mark fills less of a round tile than of a rounded square.
    fill = 0.98 if tiny else 0.8
    u = s * fill / 32.0
    pad = s * (1 - fill) / 2
    c = 16 * u

    stroke = max(1, round(1.6 * u * (1.5 if tiny else 1.0)))
    if size <= 16:
        # The two strands blur into noise at 16 px; a single ring reads cleanly.
        _ellipse(draw, pad + c, pad + c, RING_R * u, outline=STRAND_B, width=round(2.2 * u))
    else:
        for sign, colour in ((-1, STRAND_B), (1, STRAND_A)):
            pts = _strand(sign, u, c, pad)
            draw.line(pts + [pts[0]], fill=colour, width=stroke, joint="curve")

    seat_r = (2.6 if size <= 16 else 2.0 if tiny else 1.6) * u
    for k, colour in enumerate(SEATS):
        a = math.radians(-54 + 72 * k)
        _ellipse(draw, pad + c + RING_R * u * math.cos(a), pad + c + RING_R * u * math.sin(a), seat_r, fill=colour)

    if not tiny:
        halo = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        _ellipse(ImageDraw.Draw(halo), pad + c, pad + c, 4.6 * u, fill=(*TARGET[:3], 50))
        img.alpha_composite(halo)
    _ellipse(draw, pad + c, pad + c, (3.4 if tiny else 2.6) * u, fill=TARGET)

    return img.resize((size, size), Image.LANCZOS)


def write_ico(path: str, sizes: list[int]) -> None:
    """Pack a PNG-payload ICO so each entry uses the render tuned to its size.

    Pillow's ICO writer downscales a single source image, which turns the 16 px
    entry into mush; rendering per size keeps the small icons legible.
    """
    payloads = []
    for size in sizes:
        buf = io.BytesIO()
        render(size).save(buf, format="PNG")
        payloads.append(buf.getvalue())

    offset = 6 + 16 * len(sizes)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    directory = b""
    for size, payload in zip(sizes, payloads):
        directory += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0,  # palette colours
            0,  # reserved
            1,  # colour planes
            32,  # bits per pixel
            len(payload),
            offset,
        )
        offset += len(payload)

    with open(path, "wb") as fh:
        fh.write(header + directory + b"".join(payloads))


def main() -> None:
    targets = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "apple-touch-icon.png": 180,
        "android-chrome-192x192.png": 192,
        "android-chrome-512x512.png": 512,
        "mstile-150x150.png": 150,
    }
    for name, size in targets.items():
        path = os.path.join(PUBLIC, name)
        render(size).save(path)
        print(f"wrote {name} ({size}x{size})")

    write_ico(os.path.join(PUBLIC, "favicon.ico"), [16, 32, 48, 64, 128, 256])
    print("wrote favicon.ico")


if __name__ == "__main__":
    main()

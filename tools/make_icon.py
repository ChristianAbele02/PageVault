"""
Generate the PageVault Windows icon (.ico) and a PNG fallback.

The brand logo in ``static/icon.svg`` uses gradients, opacity and an SVG
drop-shadow filter that pure-Python SVG rasterisers render poorly. To keep the
build reproducible and dependency-light (Pillow only, no native cairo), the same
geometry is redrawn here at high resolution and downsampled into a multi-size
icon. Re-run whenever the brand mark changes.

Usage:
    python tools/make_icon.py
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from PIL import Image, ImageDraw

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("make_icon")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ICO = ROOT / "static" / "icon.ico"
DEFAULT_PNG = ROOT / "static" / "icon.png"

# The source SVG uses a 100 x 100 viewBox; draw at a high multiple, then downsample.
VIEWBOX = 100
SUPERSAMPLE = 1024
ICON_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
PNG_SIZE = 256

# Palette transcribed from static/icon.svg (gradients flattened to mid-tones).
COL_BG = (26, 16, 8, 255)  # #1a1008 rounded backdrop
COL_COVER = (200, 145, 58, 255)  # #c8913a book cover
COL_SPINE = (122, 80, 45, 255)  # spine, between #6b4d2e and #8a6035
COL_PAGES = (232, 221, 200, 255)  # cream page block
COL_GOLD = (212, 168, 67, 255)  # #d4a843 accent
COL_FACE = (26, 16, 8, 200)  # dark clock face, ~65% opacity
COL_GOLD_SOFT = (212, 168, 67, 150)  # faded inner ring

BACKDROP_RADIUS = 18
GROUP_OFFSET = (16, 10)  # SVG <g transform="translate(16, 10)">


def _draw_logo(size: int) -> Image.Image:
    """Render the logo into a transparent RGBA image of ``size`` px."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scale = size / VIEWBOX
    ox, oy = GROUP_OFFSET

    def s(value: float) -> float:
        return value * scale

    def poly(points: list[tuple[float, float]], fill: tuple[int, int, int, int]) -> None:
        draw.polygon([(s(x + ox), s(y + oy)) for x, y in points], fill=fill)

    def ring(cx: float, cy: float, r: float, **kwargs: object) -> None:
        box = [s(cx + ox - r), s(cy + oy - r), s(cx + ox + r), s(cy + oy + r)]
        draw.ellipse(box, **kwargs)  # type: ignore[arg-type]

    def stroke_width(w: float) -> int:
        return max(1, round(s(w)))

    # Rounded dark backdrop.
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=s(BACKDROP_RADIUS), fill=COL_BG)

    # Book: page block, spine, then cover (painter's order from the SVG).
    poly([(44, 4), (70, 6), (68, 80), (42, 78)], COL_PAGES)
    poly([(38, 4), (46, 4), (44, 78), (36, 78)], COL_SPINE)
    poly([(4, 4), (40, 4), (38, 78), (2, 78)], COL_COVER)

    # Compass/clock motif on the cover, centred at (22, 38).
    ring(22, 38, 16, fill=COL_FACE)
    ring(22, 38, 13.5, outline=COL_GOLD, width=stroke_width(1.2))
    ring(22, 38, 9, outline=COL_GOLD_SOFT, width=stroke_width(0.8))
    ring(22, 38, 4, fill=COL_GOLD)
    draw.line(
        [(s(22 + ox), s(38 + oy)), (s(22 + ox), s(25.5 + oy))],
        fill=COL_GOLD,
        width=stroke_width(1.8),
    )
    return img


def generate(ico_path: Path, png_path: Path) -> None:
    """Render the master image and write the .ico and .png outputs."""
    master = _draw_logo(SUPERSAMPLE)

    png = master.resize((PNG_SIZE, PNG_SIZE), Image.LANCZOS)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png.save(png_path, format="PNG")
    log.info("Wrote %s (%d x %d)", png_path, PNG_SIZE, PNG_SIZE)

    icon_source = master.resize((256, 256), Image.LANCZOS)
    icon_source.save(ico_path, format="ICO", sizes=ICON_SIZES)
    log.info("Wrote %s (sizes: %s)", ico_path, ", ".join(str(w) for w, _ in ICON_SIZES))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the PageVault app icon.")
    parser.add_argument("--ico", type=Path, default=DEFAULT_ICO, help="Output .ico path.")
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG, help="Output .png path.")
    args = parser.parse_args(argv)
    generate(args.ico, args.png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

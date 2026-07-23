"""Render every PageVault icon surface from one vetted vector scene.

Scene: an open book (cream pages, amber cover, rust ribbon bookmark) with a
softly-lit library of bookshelves behind it and a kraft "A.-K." tag hanging in
the clear space below the book.

This is a **development-only** tool. It needs a browser via Playwright
(``pip install playwright`` then ``playwright install msedge``) and is not run
in CI. It writes the committed icon assets:

* ``static/icon.svg`` and ``assets/icon.svg`` — square master (PWA + site)
* ``static/icon.png`` — 512px raster; ``tools/make_icon.py`` builds the Windows
  ``.ico`` from it (Pillow only, so CI needs no browser)
* the Android adaptive-icon bitmap layers under ``mipmap-xxxhdpi/``

Usage:
    python tools/render_icons.py
"""

from __future__ import annotations

import random
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SEED = 42

# Warm library palette (matches the app's design tokens).
SPINE_COLORS = [
    "#9b3a1c",
    "#b5762a",
    "#7a5c3a",
    "#5c7a5e",
    "#c8913a",
    "#8a4b2f",
    "#6b4d2e",
    "#a95d2a",
    "#48633f",
    "#7a3320",
]

DEFS = """
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#24160a"/><stop offset="1" stop-color="#120b05"/>
  </linearGradient>
  <radialGradient id="glow" cx="0.5" cy="0.62" r="0.55">
    <stop offset="0" stop-color="#c8913a" stop-opacity="0.42"/>
    <stop offset="1" stop-color="#c8913a" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vig" cx="0.5" cy="0.45" r="0.75">
    <stop offset="0.55" stop-color="#000000" stop-opacity="0"/>
    <stop offset="1" stop-color="#000000" stop-opacity="0.5"/>
  </radialGradient>
  <linearGradient id="cover" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#d4a843"/><stop offset="1" stop-color="#a56a1f"/>
  </linearGradient>
  <linearGradient id="pageL" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#f4eee0"/><stop offset="1" stop-color="#d8cbb0"/>
  </linearGradient>
  <linearGradient id="pageR" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#d8cbb0"/><stop offset="1" stop-color="#f4eee0"/>
  </linearGradient>
  <linearGradient id="gutter" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#5a4022" stop-opacity="0"/>
    <stop offset="0.5" stop-color="#3a2712" stop-opacity="0.55"/>
    <stop offset="1" stop-color="#5a4022" stop-opacity="0"/>
  </linearGradient>
  <filter id="blurBg" x="-10%" y="-10%" width="120%" height="120%">
    <feGaussianBlur stdDeviation="2.4"/>
  </filter>
  <filter id="bookShadow" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000" flood-opacity="0.55"/>
  </filter>
"""


def _shelf(x0: int, x1: int, board_y: int, min_h: int, max_h: int) -> str:
    parts = [
        f'<rect x="{x0 - 6}" y="{board_y}" width="{x1 - x0 + 12}" height="13" rx="2" fill="#241608"/>',
        f'<rect x="{x0 - 6}" y="{board_y}" width="{x1 - x0 + 12}" height="3" fill="#3a2817"/>',
    ]
    x = x0
    while x < x1 - 14:
        w = random.randint(16, 30)
        if x + w > x1:
            break
        h = random.randint(min_h, max_h)
        top = board_y - h
        colour = random.choice(SPINE_COLORS)
        parts.append(f'<rect x="{x}" y="{top}" width="{w}" height="{h}" rx="1.5" fill="{colour}"/>')
        parts.append(
            f'<rect x="{x}" y="{top}" width="3" height="{h}" fill="#fff" fill-opacity="0.10"/>'
        )
        parts.append(
            f'<rect x="{x + 3}" y="{top + h * 0.28:.0f}" width="{w - 6}" height="4" '
            f'rx="1" fill="#000" fill-opacity="0.18"/>'
        )
        x += w + random.randint(3, 7)
    return "".join(parts)


def _library() -> str:
    random.seed(SEED)  # deterministic shelves every run
    return (
        f'<g filter="url(#blurBg)" opacity="0.96">{_shelf(52, 460, 150, 70, 96)}'
        f"{_shelf(44, 468, 236, 66, 88)}</g>"
    )


def _text_lines(mirror: bool) -> str:
    out = []
    for i in range(5):
        y = 330 + i * 12
        x1, x2 = (512 - 132, 512 - 236) if mirror else (132, 236)
        out.append(
            f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y + 2}" stroke="#7a5c3a" '
            f'stroke-opacity="0.38" stroke-width="3" stroke-linecap="round"/>'
        )
    return "".join(out)


def _book() -> str:
    """The open book, ribbon and tag, drawn in the 512x512 coordinate space."""
    return f"""
    <g filter="url(#bookShadow)">
      <path d="M256 300 Q172 288 80 282 Q92 344 108 400 Q190 416 256 408
               Q322 416 404 400 Q420 344 432 282 Q340 288 256 300 Z" fill="url(#cover)"/>
      <path d="M256 300 Q172 288 80 282 Q92 344 108 400 Q190 416 256 408 L256 300 Z"
            fill="#000" fill-opacity="0.08"/>
      <path d="M96 292 Q104 344 118 394 L118 384 Q104 336 98 286 Z" fill="#cdbf9f"/>
      <path d="M416 292 Q408 344 394 394 L394 384 Q408 336 414 286 Z" fill="#cdbf9f"/>
      <path d="M256 306 Q176 296 96 288 Q104 342 118 392 Q190 404 256 400 Z" fill="url(#pageL)"/>
      <path d="M256 306 Q336 296 416 288 Q408 342 394 392 Q322 404 256 400 Z" fill="url(#pageR)"/>
      {_text_lines(False)}{_text_lines(True)}
      <rect x="246" y="300" width="20" height="102" fill="url(#gutter)"/>
      <line x1="256" y1="306" x2="256" y2="400" stroke="#2a1c0e" stroke-opacity="0.35" stroke-width="2"/>
      <path d="M256 306 Q176 296 96 288" fill="none" stroke="#fffaf0" stroke-opacity="0.5" stroke-width="2"/>
      <path d="M256 306 Q336 296 416 288" fill="none" stroke="#fffaf0" stroke-opacity="0.5" stroke-width="2"/>
      <path d="M249 300 L263 300 L262 448 L250 448 Z" fill="#9b3a1c"/>
      <path d="M256 300 L263 300 L262 448 L256 448 Z" fill="#000" fill-opacity="0.20"/>
      <path d="M247 445 h18 v5 a9 9 0 0 1 -18 0 Z" fill="#7c2f16"/>
      <line x1="256" y1="450" x2="256" y2="460" stroke="#6b4d2e" stroke-width="4"/>
      <g transform="rotate(-4 256 474)">
        <rect x="194" y="446" width="124" height="60" rx="14" fill="#f4e8ca" stroke="#8a6035" stroke-width="3.5"/>
        <rect x="194" y="446" width="124" height="20" rx="14" fill="#fff" fill-opacity="0.30"/>
        <circle cx="256" cy="461" r="6" fill="#120b05" fill-opacity="0.6"/>
        <text x="256" y="495" text-anchor="middle" font-family="Georgia, 'Times New Roman', serif"
              font-size="42" font-weight="700" letter-spacing="1.5" fill="#2a1c0e">A.-K.</text>
      </g>
    </g>"""


def full_svg(size: int) -> str:
    """Square master with the rounded tile (desktop, PWA, site)."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">
  <defs>
    <clipPath id="round"><rect x="0" y="0" width="512" height="512" rx="104"/></clipPath>
    {DEFS}
  </defs>
  <g clip-path="url(#round)">
    <rect width="512" height="512" fill="url(#bg)"/>
    {_library()}
    <rect width="512" height="512" fill="url(#vig)"/>
    <ellipse cx="256" cy="330" rx="230" ry="150" fill="url(#glow)"/>
    {_book()}
    <rect width="512" height="150" fill="#fff" fill-opacity="0.03"/>
  </g>
</svg>"""


def android_bg_svg(size: int) -> str:
    """Adaptive-icon background: dark + library, full-bleed (system masks it)."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">
  <defs>{DEFS}</defs>
  <rect width="512" height="512" fill="url(#bg)"/>
  {_library()}
  <rect width="512" height="512" fill="url(#vig)"/>
  <ellipse cx="256" cy="340" rx="240" ry="200" fill="url(#glow)"/>
</svg>"""


def android_fg_svg(size: int) -> str:
    """Adaptive-icon foreground: book + tag scaled into the central safe zone."""
    # Book+tag bbox in 512-space ~ x[80,432], y[278,506] (centre 256,392). Fit
    # into the central ~280px of the 432px layer so no mask clips it.
    scale = 0.8
    tx = 216 - scale * 256
    ty = 216 - scale * 392
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 432 432" width="{size}" height="{size}">
  <defs>{DEFS}</defs>
  <g transform="translate({tx:.1f} {ty:.1f}) scale({scale})">{_book()}</g>
</svg>"""


def _render(page: Page, svg: str, out: Path, size: int) -> None:
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(f'<!doctype html><body style="margin:0;background:transparent">{svg}</body>')
    page.wait_for_timeout(200)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.locator("svg").screenshot(path=str(out), omit_background=True)
    print(f"wrote {out.relative_to(ROOT)}")


def main() -> None:
    (ROOT / "static" / "icon.svg").write_text(full_svg(512), encoding="utf-8")
    (ROOT / "assets" / "icon.svg").write_text(full_svg(512), encoding="utf-8")
    print("wrote static/icon.svg, assets/icon.svg")

    mip = ROOT / "android/app/src/main/res/mipmap-xxxhdpi"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(device_scale_factor=1)
        _render(page, full_svg(512), ROOT / "static" / "icon.png", 512)
        _render(page, android_bg_svg(432), mip / "ic_launcher_background.png", 432)
        _render(page, android_fg_svg(432), mip / "ic_launcher_foreground.png", 432)
        browser.close()


if __name__ == "__main__":
    main()

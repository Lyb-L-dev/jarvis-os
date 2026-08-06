"""Render the final J.A.R.V.I.S logomark to PNG (pure black/white, flat)."""

from __future__ import annotations

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SIZE = 512
CX = CY = 256
R = 150
STROKE = 4
GAP_HALF = 9.0  # degrees
FONT_SIZE = 60
TRACKING = 2
TEXT = "J.A.R.V.I.S"
BASELINE = 278
FONT_PATH = r"C:\Windows\Fonts\bahnschrift.ttf"


def point(angle_deg: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return (CX + R * math.cos(a), CY + R * math.sin(a))


def draw_logo(img: Image.Image, black_bg: bool) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    if black_bg:
        d.rectangle([0, 0, SIZE, SIZE], fill=(0, 0, 0, 255))

    # top arc: 189 -> 351 (through 270/top)
    pts = []
    n = 200
    for i in range(n + 1):
        a = 189 + (351 - 189) * i / n
        pts.append(point(a))
    d.line(pts, fill=(255, 255, 255, 255), width=STROKE, joint="curve")

    # bottom arc: 9 -> 171 (through 90/bottom)
    pts = []
    for i in range(n + 1):
        a = 9 + (171 - 9) * i / n
        pts.append(point(a))
    d.line(pts, fill=(255, 255, 255, 255), width=STROKE, joint="curve")

    # wordmark with tracking
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    widths = [font.getlength(ch) for ch in TEXT]
    total = sum(widths) + TRACKING * (len(TEXT) - 1)
    x = CX - total / 2
    for ch, w in zip(TEXT, widths):
        d.text((x, BASELINE), ch, font=font, fill=(255, 255, 255, 255), anchor="ls")
        x += w + TRACKING


def render(black_bg: bool, size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if size != SIZE:
        tmp = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        draw_logo(tmp, black_bg)
        return tmp.resize((size, size), Image.LANCZOS)
    draw_logo(img, black_bg)
    return img


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else r"E:\贾维斯\docs\design"
    os.makedirs(outdir, exist_ok=True)

    render(True).save(os.path.join(outdir, "jarvis-logomark.png"))
    render(False).save(os.path.join(outdir, "jarvis-logomark-transparent.png"))

    # preview panel: logo + sizes on pure black
    W, H = 1200, 640
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    logo = render(False, 360)
    panel.alpha_composite(logo, (W // 2 - 180, 40))
    x = W // 2 - 150
    for s in (96, 48, 24, 16):
        small = render(False, s)
        panel.alpha_composite(small, (x, 470))
        x += s + 40
    panel.convert("RGB").save(os.path.join(outdir, "jarvis-logomark-preview.png"))
    print("logomark rendered ok")


if __name__ == "__main__":
    main()

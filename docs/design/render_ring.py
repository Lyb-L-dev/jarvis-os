"""Render the 'JARVIS Ring' brand mark (thin ellipse + wordmark) to PNG."""

from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CANVAS = 2048
OUT = 512
U = CANVAS / 64

GEIST_CANDIDATES = [
    r"apps/web/node_modules/geist/dist/fonts/geist-sans/GeistSans-SemiBold.ttf",
    r"apps/web/node_modules/geist/dist/fonts/geist-sans/GeistSans-Bold.ttf",
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\msyhbd.ttc",
]


def new_layer() -> Image.Image:
    return Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))


def radial(size: int, stops, center=(0.5, 0.5), max_r=0.5) -> Image.Image:
    cx = center[0] * size
    cy = center[1] * size
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    dmax = max_r * size
    t = np.clip(d / dmax, 0.0, 1.0)
    out = np.zeros((size, size, 4), np.float32)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        mask = (t >= t0) & (t <= t1)
        tt = np.clip((t[mask] - t0) / max(t1 - t0, 1e-6), 0.0, 1.0)
        for ch in range(4):
            out[mask, ch] = c0[ch] * (1 - tt) + c1[ch] * tt
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def bloom(img: Image.Image, layer: Image.Image, radius: float) -> None:
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)))
    img.alpha_composite(layer)


def load_font(px_size: int):
    for c in GEIST_CANDIDATES:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, px_size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_ring_mark(img: Image.Image, text_color, glow_color, ring_color) -> None:
    cx = cy = 32
    rx_u, ry_u = 22.6, 17.9  # ratio ~1.26 like reference

    # soft ambient halo
    halo = radial(
        CANVAS,
        [(0.0, (*glow_color, 30)), (0.55, (*glow_color, 8)), (1.0, (*glow_color, 0))],
        max_r=0.62,
    )
    img.alpha_composite(halo)

    # thin ellipse ring with glow
    ring = new_layer()
    rd = ImageDraw.Draw(ring, "RGBA")
    rd.ellipse(
        [(cx - rx_u) * U, (cy - ry_u) * U, (cx + rx_u) * U, (cy + ry_u) * U],
        outline=(*ring_color, 255),
        width=max(2, int(1.5 * U)),
    )
    bloom(img, ring, 1.4 * U)

    # wordmark, centered
    font = load_font(int(9.2 * U))
    tracking = 0.85 * U
    text = "JARVIS"
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x_start = cx * U - total / 2
    y_start = cy * U - font.size * 0.36  # optical center

    txt = new_layer()
    td = ImageDraw.Draw(txt, "RGBA")
    x = x_start
    for ch, w in zip(text, widths):
        td.text((x, y_start), ch, font=font, fill=(*text_color, 255))
        x += w + tracking
    bloom(img, txt, 1.0 * U)


def render_variant(style: str, size: int = OUT) -> Image.Image:
    img = new_layer()
    if style == "white":
        draw_ring_mark(img, (246, 254, 255), (120, 235, 250), (235, 250, 255))
    elif style == "cyan":
        draw_ring_mark(img, (233, 251, 255), (34, 211, 238), (86, 229, 255))
    else:
        raise ValueError(style)
    return img.resize((size, size), Image.LANCZOS)


def load_ui_font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\segoeuib.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else r"docs/design"
    os.makedirs(outdir, exist_ok=True)

    white = render_variant("white")
    cyan = render_variant("cyan")
    white.save(os.path.join(outdir, "jarvis-ring-white.png"))
    cyan.save(os.path.join(outdir, "jarvis-ring-cyan.png"))

    W, H = 1480, 860
    panel = Image.new("RGBA", (W, H), (7, 7, 10, 255))
    d = ImageDraw.Draw(panel, "RGBA")

    def ambient(cx, cy, r, color, peak):
        gl = radial(
            W,
            [(0.0, (*color, int(255 * peak))), (1.0, (*color, 0))],
            center=(cx / W, cy / W),
            max_r=r / W,
        )
        panel.alpha_composite(gl)

    ambient(1150, 140, 500, (34, 211, 238), 0.05)
    ambient(280, 760, 480, (99, 102, 241), 0.04)

    d.text((60, 44), "JARVIS Ring · 环形字标", font=load_ui_font(34, bold=True), fill=(244, 244, 245, 255))
    d.text((60, 96), "细椭圆环 + 居中字标，贴近你给的参考图", font=load_ui_font(19), fill=(138, 143, 156, 255))

    cards = [(80, 160), (780, 160), (80, 520)]
    styles = ["white", "cyan"]
    labels = {
        "white": "纯白 · 贴近原图",
        "cyan": "青白 · 贴合 Jarvis 能源色",
    }
    notes = {
        "white": "环与字均为白色，带柔和光晕",
        "cyan": "环与光晕带青色，字为冷白",
    }
    for idx, ((v, (x, y))) in enumerate(zip(styles, cards)):
        d.rounded_rectangle(
            [x, y, x + 620, y + 310],
            radius=32,
            fill=(16, 22, 28, 210),
            outline=(255, 255, 255, 22),
            width=2,
        )
        mark = white if v == "white" else cyan
        panel.alpha_composite(mark.resize((240, 240), Image.LANCZOS), (x + 40, y + 30))
        d.text((x + 320, y + 60), labels[v], font=load_ui_font(26, bold=True), fill=(240, 246, 250, 255))
        d.text((x + 322, y + 108), notes[v], font=load_ui_font(18), fill=(138, 143, 156, 255))
        d.text((x + 40, y + 262), f"候选 {idx + 1}", font=load_ui_font(18, bold=True), fill=(165, 243, 252, 255))

    # favicon / sizes row in third card
    x, y = cards[2]
    d.rounded_rectangle(
        [x, y, x + 620, y + 310],
        radius=32,
        fill=(16, 22, 28, 210),
        outline=(255, 255, 255, 22),
        width=2,
    )
    sizes = [96, 48, 24, 16]
    sx = x + 40
    for s in sizes:
        small = cyan.resize((s, s), Image.LANCZOS)
        panel.alpha_composite(small, (sx, y + 40))
        sx += s + 40
    d.text((x + 40, y + 170), "尺寸测试（96 / 48 / 24 / 16 px）", font=load_ui_font(19), fill=(240, 246, 250, 255))
    d.text((x + 40, y + 208), "环细字稳，小尺寸依然可读", font=load_ui_font(17), fill=(138, 143, 156, 255))
    d.text((x + 40, y + 262), "候选 3 · 小尺寸", font=load_ui_font(18, bold=True), fill=(165, 243, 252, 255))

    panel.convert("RGB").save(os.path.join(outdir, "jarvis-ring-preview.png"))
    print("ring variants rendered ok")


if __name__ == "__main__":
    main()

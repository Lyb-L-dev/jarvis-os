"""Render Jarvis brand mark variants (Reacto / Aurora / Network) to PNG."""

from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CANVAS = 1024  # supersampled
OUT = 512
U = CANVAS / 64  # units per viewBox unit


def new_layer() -> Image.Image:
    return Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))


def radial(size: int, stops, center=(0.5, 0.5), max_r=0.5) -> Image.Image:
    """Radial gradient. stops: [(t, (r,g,b,a))]."""
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
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    img.alpha_composite(blurred)
    img.alpha_composite(layer)


def glow_line(img: Image.Image, pts, width_u, color, glow_u, alpha=255) -> None:
    layer = new_layer()
    d = ImageDraw.Draw(layer, "RGBA")
    width = max(1, int(width_u * U))
    d.line(pts, fill=(*color, alpha), width=width)
    if glow_u > 0:
        bloom(img, layer, glow_u * U)
    else:
        img.alpha_composite(layer)


def glow_circle(img: Image.Image, cx, cy, r_u, color, alpha, glow_u) -> None:
    layer = new_layer()
    d = ImageDraw.Draw(layer, "RGBA")
    r = r_u * U
    d.ellipse([cx * U - r, cy * U - r, cx * U + r, cy * U + r], fill=(*color, alpha))
    bloom(img, layer, glow_u * U)


def glow_ring(img: Image.Image, cx, cy, r_u, width_u, color, alpha, glow_u) -> None:
    layer = new_layer()
    d = ImageDraw.Draw(layer, "RGBA")
    r = r_u * U
    w = max(1, int(width_u * U))
    d.ellipse(
        [cx * U - r, cy * U - r, cx * U + r, cy * U + r],
        outline=(*color, alpha),
        width=w,
    )
    bloom(img, layer, glow_u * U)


def draw_reactor(img: Image.Image) -> None:
    cx = cy = 32
    cyan = (86, 229, 255)
    bright = (197, 248, 255)
    white = (240, 254, 255)

    # soft ambient glow
    halo = radial(
        CANVAS,
        [(0.0, (34, 211, 238, 46)), (0.55, (34, 211, 238, 12)), (1.0, (34, 211, 238, 0))],
        max_r=0.62,
    )
    img.alpha_composite(halo)

    # radial beams between rings
    beams = new_layer()
    bd = ImageDraw.Draw(beams, "RGBA")
    for k in range(12):
        ang = math.radians(k * 30)
        x0 = cx + 16.5 * math.cos(ang)
        y0 = cy + 16.5 * math.sin(ang)
        x1 = cx + 26 * math.cos(ang)
        y1 = cy + 26 * math.sin(ang)
        bd.line(
            [(x0 * U, y0 * U), (x1 * U, y1 * U)],
            fill=(*cyan, 70),
            width=max(1, int(0.55 * U)),
        )
    bloom(img, beams, 1.2 * U)

    # outer ring
    glow_ring(img, cx, cy, 27, 1.1, cyan, 150, 2.6)
    # segmented ring
    seg = new_layer()
    sd = ImageDraw.Draw(seg, "RGBA")
    for k in range(3):
        start = k * 120 + 10
        end = start + 100
        sd.arc(
            [(cx - 21) * U, (cy - 21) * U, (cx + 21) * U, (cy + 21) * U],
            start,
            end,
            fill=(*bright, 215),
            width=max(1, int(1.3 * U)),
        )
    bloom(img, seg, 2.0 * U)
    # dashed inner ring
    dash = new_layer()
    dd = ImageDraw.Draw(dash, "RGBA")
    for k in range(20):
        start = k * 18 + 2
        end = start + 6
        dd.arc(
            [(cx - 15) * U, (cy - 15) * U, (cx + 15) * U, (cy + 15) * U],
            start,
            end,
            fill=(*cyan, 160),
            width=max(1, int(0.8 * U)),
        )
    bloom(img, dash, 1.1 * U)

    # orbiting particles
    glow_circle(img, cx + 27 * math.cos(math.radians(28)), cy + 27 * math.sin(math.radians(28)), 1.1, white, 255, 4.0)
    glow_circle(img, cx + 15 * math.cos(math.radians(205)), cy + 15 * math.sin(math.radians(205)), 0.8, bright, 230, 3.2)

    # core
    core = radial(
        CANVAS,
        [
            (0.0, (255, 255, 255, 255)),
            (0.28, (226, 250, 255, 255)),
            (0.6, (110, 230, 250, 235)),
            (0.85, (24, 168, 200, 150)),
            (1.0, (10, 90, 120, 0)),
        ],
        center=(0.5, 0.48),
        max_r=0.16,
    )
    bloom(img, core, 4.5)
    glow_circle(img, cx, cy, 2.5, white, 255, 2.0)


def draw_aurora(img: Image.Image) -> None:
    cx = cy = 32
    cyan = (94, 231, 250)
    bright = (205, 250, 255)
    white = (240, 254, 255)

    halo = radial(
        CANVAS,
        [(0.0, (34, 211, 238, 40)), (0.5, (34, 211, 238, 10)), (1.0, (34, 211, 238, 0))],
        max_r=0.6,
    )
    img.alpha_composite(halo)

    # sphere with smooth gradient
    sphere = radial(
        CANVAS,
        [
            (0.0, (233, 253, 255, 235)),
            (0.35, (160, 240, 252, 225)),
            (0.7, (62, 196, 228, 200)),
            (0.92, (18, 96, 128, 170)),
            (1.0, (10, 45, 66, 120)),
        ],
        center=(0.5, 0.42),
        max_r=0.28,
    )
    bloom(img, sphere, 1.6)
    glow_ring(img, cx, cy, 17.2, 0.8, bright, 150, 2.4)

    # two tilted orbit ellipses with glow
    for angle, alpha in ((-24, 150), (24, 120)):
        layer = new_layer()
        d = ImageDraw.Draw(layer, "RGBA")
        d.ellipse(
            [(cx - 26) * U, (cy - 9) * U, (cx + 26) * U, (cy + 9) * U],
            outline=(*cyan, alpha),
            width=max(1, int(0.9 * U)),
        )
        layer = layer.rotate(angle, resample=Image.BICUBIC, center=(cx * U, cy * U))
        bloom(img, layer, 1.8 * U)

    # particles on the ellipses
    for ang_deg, big in ((40, True), (160, False), (300, False)):
        ang = math.radians(ang_deg)
        px = cx + 26 * math.cos(ang)
        py = cy + 9 * math.sin(ang)
        # rotate point by -24 deg around center
        px2 = cx + (px - cx) * math.cos(math.radians(-24)) - (py - cy) * math.sin(math.radians(-24))
        py2 = cy + (px - cx) * math.sin(math.radians(-24)) + (py - cy) * math.cos(math.radians(-24))
        glow_circle(img, px2, py2, 1.2 if big else 0.8, white if big else bright, 255, 4.2 if big else 3.0)

    # core
    core = radial(
        CANVAS,
        [
            (0.0, (255, 255, 255, 255)),
            (0.3, (230, 251, 255, 255)),
            (0.65, (120, 234, 250, 220)),
            (0.9, (30, 175, 205, 120)),
            (1.0, (12, 100, 130, 0)),
        ],
        center=(0.5, 0.47),
        max_r=0.13,
    )
    bloom(img, core, 4.0)
    glow_circle(img, cx, cy, 2.4, white, 255, 1.8)


def draw_network(img: Image.Image) -> None:
    cx = cy = 32
    cyan = (86, 229, 255)
    bright = (197, 248, 255)
    white = (240, 254, 255)

    halo = radial(
        CANVAS,
        [(0.0, (34, 211, 238, 42)), (0.5, (34, 211, 238, 10)), (1.0, (34, 211, 238, 0))],
        max_r=0.62,
    )
    img.alpha_composite(halo)

    # sphere shell + faint grid
    sphere = radial(
        CANVAS,
        [
            (0.0, (216, 250, 255, 150)),
            (0.55, (58, 190, 225, 110)),
            (0.85, (20, 110, 145, 90)),
            (1.0, (8, 42, 60, 70)),
        ],
        center=(0.5, 0.45),
        max_r=0.28,
    )
    img.alpha_composite(sphere)
    glow_ring(img, cx, cy, 16.5, 0.9, bright, 140, 2.2)
    grid = new_layer()
    gd = ImageDraw.Draw(grid, "RGBA")
    r = 16.5 * U
    gd.ellipse([(cx - 13.8) * U, cy * U - r, (cx + 13.8) * U, cy * U + r], outline=(*cyan, 55), width=max(1, int(0.55 * U)))
    gd.ellipse([cx * U - r, (cy - 5.4) * U, cx * U + r, (cy + 5.4) * U], outline=(*cyan, 55), width=max(1, int(0.55 * U)))
    bloom(img, grid, 0.6 * U)

    # two great-circle arcs with glow
    def arc_path(flat: float, tilt_deg: float, alpha: int) -> None:
        layer = new_layer()
        d = ImageDraw.Draw(layer, "RGBA")
        d.ellipse(
            [(cx - 25) * U, (cy - 25 * flat) * U, (cx + 25) * U, (cy + 25 * flat) * U],
            outline=(*bright, alpha),
            width=max(1, int(0.8 * U)),
        )
        layer = layer.rotate(tilt_deg, resample=Image.BICUBIC, center=(cx * U, cy * U))
        bloom(img, layer, 1.5 * U)

    arc_path(0.42, -30, 110)
    arc_path(0.42, 30, 80)

    # nodes + spokes + chords
    outer = [(cx + 13 * math.cos(math.radians(a)), cy + 13 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    links = new_layer()
    ld = ImageDraw.Draw(links, "RGBA")
    lw = max(1, int(0.7 * U))
    for x, y in outer:
        ld.line([(cx * U, cy * U), (x * U, y * U)], fill=(*cyan, 100), width=lw)
    for i in range(6):
        x1, y1 = outer[i]
        x2, y2 = outer[(i + 1) % 6]
        ld.line([(x1 * U, y1 * U), (x2 * U, y2 * U)], fill=(*cyan, 65), width=lw)
    bloom(img, links, 0.9 * U)

    for i, (x, y) in enumerate(outer):
        glow_circle(img, x, y, 1.25, white if i % 2 == 0 else bright, 255, 3.4)

    # core
    core = radial(
        CANVAS,
        [
            (0.0, (255, 255, 255, 255)),
            (0.3, (230, 251, 255, 255)),
            (0.65, (120, 234, 250, 225)),
            (0.9, (30, 175, 205, 130)),
            (1.0, (12, 100, 130, 0)),
        ],
        center=(0.5, 0.47),
        max_r=0.13,
    )
    bloom(img, core, 4.0)
    glow_circle(img, cx, cy, 2.4, white, 255, 1.8)


def load_font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\arialbd.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def render(variant: str, size: int = OUT) -> Image.Image:
    img = new_layer()
    if variant == "reactor":
        draw_reactor(img)
    elif variant == "aurora":
        draw_aurora(img)
    elif variant == "network":
        draw_network(img)
    else:
        raise ValueError(variant)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else r"E:\贾维斯\docs\design"
    os.makedirs(outdir, exist_ok=True)

    variants = ["reactor", "aurora", "network"]
    labels = {
        "reactor": "Reactor · 方舟能量核心",
        "aurora": "Aurora · 极光核心",
        "network": "Network · 万物互联球",
    }
    notes = {
        "reactor": "同心环 + 旋转粒子 + 强核心光，弧反应堆式科技感",
        "aurora": "极简球体 + 双轨道弧 + 三粒子，电影式留白与优雅",
        "network": "球壳 + 六节点 + 信息弧线，保留万物互联语义",
    }

    marks = {}
    for v in variants:
        marks[v] = render(v, 512)
        marks[v].save(os.path.join(outdir, f"jarvis-{v}.png"))

    # comparison panel: 2x2 (3 variants + classic)
    W, H = 1480, 980
    panel = Image.new("RGBA", (W, H), (7, 7, 10, 255))
    d = ImageDraw.Draw(panel, "RGBA")

    # ambient glows
    def ambient(cx, cy, r, color, peak):
        gl = radial(
            W,
            [(0.0, (color[0], color[1], color[2], int(255 * peak))), (1.0, (color[0], color[1], color[2], 0))],
            center=(cx / W, cy / W),
            max_r=r / W,
        )
        panel.alpha_composite(gl)

    ambient(1150, 150, 500, (34, 211, 238), 0.05)
    ambient(300, 850, 520, (99, 102, 241), 0.04)

    d.text((60, 44), "Jarvis Brand Mark · 设计候选", font=load_font(34, bold=True), fill=(244, 244, 245, 255))
    d.text((60, 96), "三个方向，选择后继续打磨并接入前端", font=load_font(19), fill=(138, 143, 156, 255))

    cards = [(80, 160), (780, 160), (80, 570), (780, 570)]
    order = ["reactor", "aurora", "network"]
    for idx, (v, (x, y)) in enumerate(zip(order + [None], cards)):
        d.rounded_rectangle(
            [x, y, x + 620, y + 360],
            radius=32,
            fill=(16, 22, 28, 210),
            outline=(255, 255, 255, 22),
            width=2,
        )
        if v:
            panel.alpha_composite(marks[v].resize((250, 250), Image.LANCZOS), (x + 40, y + 40))
            d.text((x + 320, y + 70), labels[v], font=load_font(26, bold=True), fill=(240, 246, 250, 255))
            d.text((x + 322, y + 118), notes[v], font=load_font(18), fill=(138, 143, 156, 255))
            d.text((x + 40, y + 314), f"候选 {idx + 1}", font=load_font(18, bold=True), fill=(165, 243, 252, 255))
        else:
            classic = Image.open(os.path.join(outdir, "jarvis-network-mark.png")).convert("RGBA").resize((250, 250), Image.LANCZOS)
            panel.alpha_composite(classic, (x + 40, y + 40))
            d.text((x + 320, y + 70), "Classic · 上一版", font=load_font(26, bold=True), fill=(240, 246, 250, 255))
            d.text((x + 322, y + 118), "线路图风格，保留作对比", font=load_font(18), fill=(138, 143, 156, 255))
            d.text((x + 40, y + 314), "上一版", font=load_font(18, bold=True), fill=(138, 143, 156, 255))

    panel.convert("RGB").save(os.path.join(outdir, "jarvis-variants.png"))
    print("variants rendered ok")


if __name__ == "__main__":
    main()

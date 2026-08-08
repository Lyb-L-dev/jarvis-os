"""Render the Jarvis Network Core mark + preview panel to PNG."""

from __future__ import annotations

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

S = 16  # supersample factor: 64 viewBox * 16 = 1024 px


def px(v: float) -> float:
    return v * S


def hexc(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def with_alpha(color: tuple[int, int, int], a: int) -> tuple[int, int, int, int]:
    return (*color, a)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def draw_glow(img: Image.Image, cx: float, cy: float, r: float, color: tuple[int, int, int], peak: float = 0.22) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    steps = max(8, int(r * 0.35))
    for i in range(steps, 0, -1):
        rr = r * i / steps
        a = int(255 * peak * (i / steps) ** 2.2)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=with_alpha(color, a))


def draw_core(img: Image.Image, cx: float, cy: float, r: float) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    stops = [
        (0.0, hexc("#E8FDFF")),
        (0.4, hexc("#7EE7F8")),
        (0.75, hexc("#22D3EE")),
        (1.0, hexc("#0E7490")),
    ]
    steps = max(12, int(r * 0.5))
    for i in range(steps, 0, -1):
        t = 1 - i / steps
        rr = r * i / steps
        seg = 0
        while seg < len(stops) - 2 and t > stops[seg + 1][0]:
            seg += 1
        t0, c0 = stops[seg]
        t1, c1 = stops[seg + 1]
        tt = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
        col = lerp(c0, c1, tt)
        a = int(255 * (i / steps) ** 0.85)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=with_alpha(col, a))


def quad_sample(p0, c, p1, n=48):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * c[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * c[1] + t * t * p1[1]
        pts.append((x, y))
    return pts


def draw_mark(canvas_img: Image.Image) -> None:
    d = ImageDraw.Draw(canvas_img, "RGBA")
    cx, cy = px(32), px(32)
    cyan = hexc("#22D3EE")
    cyan_l = hexc("#57D9F2")
    cyan_h = hexc("#A5F3FC")
    white = hexc("#E8FDFF")

    draw_glow(canvas_img, cx, cy, px(28), cyan, peak=0.22)

    r = px(18.5)
    d.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=with_alpha(hexc("#071820"), 158),
        outline=with_alpha(hexc("#3FD6F0"), 115),
        width=max(2, int(px(1.1))),
    )
    for rx, alpha in ((16, 40), (9, 33)):
        d.ellipse(
            [cx - px(rx), cy - r, cx + px(rx), cy + r],
            outline=with_alpha(cyan, alpha),
            width=max(1, int(px(0.7))),
        )
    for ry, alpha in ((6.5, 40), (12.5, 33)):
        d.ellipse(
            [cx - r, cy - px(ry), cx + r, cy + px(ry)],
            outline=with_alpha(cyan, alpha),
            width=max(1, int(px(0.7))),
        )

    arc1 = quad_sample((px(46.5), cy), (cx, px(2)), (px(17.5), cy))
    d.line(arc1, fill=with_alpha(cyan_h, 128), width=max(1, int(px(0.9))))
    arc2 = quad_sample((cx, px(46.5)), (px(62), cy), (cx, px(17.5)))
    d.line(arc2, fill=with_alpha(cyan_h, 128), width=max(1, int(px(0.9))))

    outer = [
        (46.5, 32), (42.25, 42.25), (32, 46.5), (21.75, 42.25),
        (17.5, 32), (21.75, 21.75), (32, 17.5), (42.25, 21.75),
    ]
    inner = [(37.66, 37.66), (26.34, 37.66), (26.34, 26.34), (37.66, 26.34)]

    lw = max(1, int(px(0.9)))
    for x, y in outer + inner:
        d.line([(cx, cy), (px(x), px(y))], fill=with_alpha(cyan_l, 150), width=lw)
    for i in range(8):
        x1, y1 = outer[i]
        x2, y2 = outer[(i + 1) % 8]
        d.line([(px(x1), px(y1)), (px(x2), px(y2))], fill=with_alpha(cyan_l, 150), width=lw)
    for i in range(4):
        x1, y1 = inner[i]
        x2, y2 = inner[(i + 1) % 4]
        d.line([(px(x1), px(y1)), (px(x2), px(y2))], fill=with_alpha(cyan_l, 120), width=lw)

    for x, y in outer:
        d.ellipse(
            [px(x) - px(1.8), px(y) - px(1.8), px(x) + px(1.8), px(y) + px(1.8)],
            fill=with_alpha(cyan_h, 255),
            outline=with_alpha(cyan, 200),
            width=max(1, int(px(0.6))),
        )
    for x, y in inner:
        d.ellipse(
            [px(x) - px(1.3), px(y) - px(1.3), px(x) + px(1.3), px(y) + px(1.3)],
            fill=with_alpha(hexc("#67E8F9"), 255),
            outline=with_alpha(cyan, 180),
            width=max(1, int(px(0.5))),
        )

    draw_core(canvas_img, cx, cy, px(6))
    d.ellipse([cx - px(2.6), cy - px(2.6), cx + px(2.6), cy + px(2.6)], fill=white)


def render_mark(size: int = 512, bg=None) -> Image.Image:
    img = Image.new("RGBA", (64 * S, 64 * S), (0, 0, 0, 0))
    draw_mark(img)
    img = img.resize((size, size), Image.LANCZOS)
    if bg:
        bgimg = Image.new("RGBA", (size, size), bg)
        bgimg.alpha_composite(img)
        return bgimg
    return img


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else r"docs/design"
    os.makedirs(outdir, exist_ok=True)

    mark = render_mark(512)
    mark.save(os.path.join(outdir, "jarvis-network-mark.png"))

    W, H = 1280, 800
    panel = Image.new("RGBA", (W, H), (7, 7, 10, 255))
    d = ImageDraw.Draw(panel, "RGBA")
    draw_glow(panel, 980, 120, 420, hexc("#22D3EE"), peak=0.05)
    draw_glow(panel, 260, 700, 460, hexc("#6366F1"), peak=0.04)

    d.rounded_rectangle(
        [60, 60, W - 60, H - 60],
        radius=56,
        fill=with_alpha(hexc("#10161C"), 200),
        outline=with_alpha(hexc("#FFFFFF"), 20),
        width=2,
    )

    mark_lg = render_mark(540)
    panel.alpha_composite(mark_lg, (120, 130))

    f_big = load_font(64, bold=True)
    f_sub = load_font(26)
    f_tag = load_font(20)
    f_note = load_font(20)
    d.text((760, 260), "Jarvis OS", font=f_big, fill=(244, 244, 245, 255))
    d.text((762, 360), "Jarvis Network Core · 万物互联呼吸球", font=f_sub, fill=(138, 143, 156, 255))
    d.rounded_rectangle(
        [762, 430, 1102, 480],
        radius=25,
        fill=with_alpha(hexc("#22D3EE"), 16),
        outline=with_alpha(hexc("#22D3EE"), 60),
        width=2,
    )
    d.text((790, 446), "待命 IDLE · 4.2s 呼吸周期", font=f_tag, fill=(165, 243, 252, 255))
    d.text((762, 520), "核心 = Jarvis 能源之光", font=f_note, fill=(138, 143, 156, 255))
    d.text((762, 556), "环绕节点与弧线 = 记忆 / 情报 / 成长 / 工具", font=f_note, fill=(138, 143, 156, 255))
    d.text((762, 592), "节点脉冲 = 各 Agent 与模块的活动", font=f_note, fill=(138, 143, 156, 255))

    x = 760
    for s in (96, 48, 24, 16):
        small = render_mark(s)
        panel.alpha_composite(small, (x, 660))
        x += s + 36

    panel.convert("RGB").save(os.path.join(outdir, "jarvis-network-preview.png"))
    print("rendered ok")


if __name__ == "__main__":
    main()

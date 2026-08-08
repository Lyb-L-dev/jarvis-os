"""Crop + binarize the user's reference image into a clean flat B&W logomark."""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageFilter


def main() -> None:
    src = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else r"docs/design"
    os.makedirs(outdir, exist_ok=True)

    im = Image.open(src).convert("RGB")
    g = im.convert("L")
    mask = g.point(lambda v: 255 if v > 40 else 0)
    bbox = mask.getbbox()
    assert bbox, "no bright content found"
    x0, y0, x1, y1 = bbox
    cxm = (x0 + x1) / 2
    cym = (y0 + y1) / 2
    side = int(max(x1 - x0, y1 - y0) * 1.06)
    half = side // 2
    xa = max(0, int(cxm) - half)
    ya = max(0, int(cym) - half)
    xb = min(im.width, xa + side)
    yb = min(im.height, ya + side)
    crop = im.crop((xa, ya, xb, yb)).resize((1024, 1024), Image.LANCZOS)
    crop = crop.filter(ImageFilter.GaussianBlur(0.5))
    gray = crop.convert("L")

    # binarize: white lines on pure black
    bin_img = gray.point(lambda v: 255 if v > 70 else 0)
    black = Image.new("RGB", (1024, 1024), (0, 0, 0))
    black.paste(Image.merge("RGB", [bin_img, bin_img, bin_img]), (0, 0), bin_img)
    black.save(os.path.join(outdir, "jarvis-logomark-user.png"))

    # transparent version: white on alpha
    rgba = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    rgba.paste(Image.merge("RGBA", [bin_img, bin_img, bin_img, bin_img]), (0, 0))
    rgba.save(os.path.join(outdir, "jarvis-logomark-user-transparent.png"))

    # sizes preview on pure black
    W, H = 1200, 640
    panel = Image.new("RGB", (W, H), (0, 0, 0))
    logo = black.resize((360, 360), Image.LANCZOS)
    panel.paste(logo, (W // 2 - 180, 40))
    x = W // 2 - 150
    for s in (96, 48, 24, 16):
        small = black.resize((s, s), Image.LANCZOS)
        panel.paste(small, (x, 470))
        x += s + 40
    panel.save(os.path.join(outdir, "jarvis-logomark-user-preview.png"))
    print("user image processed ok", "crop", (xa, ya, xb, yb), "bright", bbox)


if __name__ == "__main__":
    main()

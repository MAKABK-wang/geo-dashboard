#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the social share image and touch icon (optional, needs Pillow).

Committed PNGs are part of the repository, so a normal build does not need
Pillow. Re-run this only when the cover copy changes:

    python scripts/make_assets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    print("Pillow is required: pip install Pillow", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

FONT_CANDIDATES = {
    "bold": [
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ],
    "regular": [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ],
    "mono": [
        "C:/Windows/Fonts/consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
}

ACCENT = (109, 155, 255)
CYAN = (90, 216, 255)
DANGER = (255, 107, 136)
WARN = (247, 185, 85)
SUCCESS = (61, 220, 151)
TEXT = (233, 238, 249)
MUTED = (154, 170, 199)
FAINT = (110, 126, 154)


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[kind]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def vertical_gradient(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def add_glow(image: Image.Image, center: tuple[int, int], radius: int, color: tuple, alpha: int) -> Image.Image:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x, y = center
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    return Image.alpha_composite(image.convert("RGBA"), layer)


def add_grid(image: Image.Image, step: int = 48, alpha: int = 12) -> Image.Image:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for x in range(0, image.width, step):
        draw.line([(x, 0), (x, image.height)], fill=(148, 175, 230, alpha), width=1)
    for y in range(0, image.height, step):
        draw.line([(0, y), (image.width, y)], fill=(148, 175, 230, alpha), width=1)
    return Image.alpha_composite(image, layer)


def draw_logo(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    scale = size / 32
    points = [
        (16 * scale + x, 2.8 * scale + y),
        (27.4 * scale + x, 9 * scale + y),
        (27.4 * scale + x, 23 * scale + y),
        (16 * scale + x, 29.2 * scale + y),
        (4.6 * scale + x, 23 * scale + y),
        (4.6 * scale + x, 9 * scale + y),
    ]
    draw.polygon(points, outline=ACCENT, width=max(2, round(1.6 * scale)))
    for offset, top in ((10.5, 15.3), (16, 10.5), (21.5, 13.1)):
        draw.line(
            [
                (offset * scale + x, 19.5 * scale + y),
                (offset * scale + x, top * scale + y),
            ],
            fill=CYAN,
            width=max(3, round(2.2 * scale)),
        )


def make_cover() -> None:
    width, height = 1200, 630
    image = vertical_gradient(width, height, (6, 10, 19), (12, 22, 40))
    image = add_glow(image, (120, -40), 420, (77, 125, 255), 90)
    image = add_glow(image, (1090, 80), 330, (90, 216, 255), 40)
    image = add_grid(image)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([22, 22, width - 22, height - 22], radius=26, outline=(34, 52, 82), width=2)

    draw_logo(draw, 72, 66, 46)

    eyebrow_font = load_font("mono", 17)
    draw.text((136, 76), "OPEN GEO REPORT  /  2026-10-31", font=eyebrow_font, fill=(126, 176, 255))

    title_font = load_font("bold", 66)
    draw.text((72, 150), "GEO 可视化仪表盘", font=title_font, fill=TEXT)

    subtitle_font = load_font("regular", 30)
    draw.text((74, 242), "合一自动化 · AI 搜索可见性公开报告", font=subtitle_font, fill=MUTED)

    draw.line([(72, 318), (width - 72, 318)], fill=(38, 56, 88), width=1)

    stats = [
        ("0%", "品牌提及率", DANGER),
        ("0%", "域名引用率", DANGER),
        ("2/6", "站点可读性", WARN),
        ("30", "条 FAQ 可检索", SUCCESS),
    ]
    number_font = load_font("bold", 52)
    label_font = load_font("regular", 19)
    x = 72
    for number, label, color in stats:
        draw.text((x, 368), number, font=number_font, fill=color)
        draw.text((x, 436), label, font=label_font, fill=FAINT)
        x += 270

    draw.line([(72, 512), (width - 72, 512)], fill=(30, 46, 74), width=1)
    footer_font = load_font("regular", 19)
    draw.text((72, 542), "公开数据 · CC BY 4.0 · 任何人可检索与引用", font=footer_font, fill=MUTED)
    domain_font = load_font("mono", 18)
    draw.text((width - 72, 544), "visionheyi.com", font=domain_font, fill=FAINT, anchor="ra")

    image.convert("RGB").save(ASSETS / "og-cover.png", optimize=True)
    print("wrote", ASSETS / "og-cover.png", f"{width}x{height}")


def make_touch_icon() -> None:
    size = 180
    image = Image.new("RGBA", (size, size), (11, 18, 34, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=40, fill=(11, 18, 34, 255))
    draw_logo(draw, 30, 30, 120)
    image.save(ASSETS / "apple-touch-icon.png", optimize=True)
    print("wrote", ASSETS / "apple-touch-icon.png", f"{size}x{size}")


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    make_cover()
    make_touch_icon()

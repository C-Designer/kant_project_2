"""Build the 1200x630 link-preview image (frontend/public/og.png).

Layout 1 from docs/design/brand-ppt/og-sheet.jpg: headline left, a fan of three
original illustration cells right. Cells are cut from the user's sheet, never redrawn.

    uv run --with pillow python scripts/build_og_image.py [--fonts ~/Library/Fonts]
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "frontend"
W, H = 1200, 630
CREAM, PINK, COCOA, MUTED = "#FEFBF4", "#F0607E", "#2B241F", "#7A6A5E"
PICKS = ["T03", "T13", "T06"]  # back → front: 탐험 메이트, 찰떡 팀워크, 포근한 둥지


def heart(size: int, color: str) -> Image.Image:
    s = size * 4  # draw large, downsample for smooth edges
    im = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(im)
    r = s // 4
    d.ellipse([0, 0, 2 * r, 2 * r], fill=color)
    d.ellipse([2 * r, 0, 4 * r, 2 * r], fill=color)
    d.polygon([(0, r + r // 3), (s, r + r // 3), (s // 2, s - 2)], fill=color)
    return im.resize((size, size), Image.LANCZOS)


def card(sheet: Image.Image, crop: dict, width: int) -> Image.Image:
    cell = sheet.crop((crop["x"], crop["y"], crop["x"] + crop["width"], crop["y"] + crop["height"]))
    cell = cell.resize((width, round(width * crop["height"] / crop["width"])), Image.LANCZOS)
    pad, radius = 10, 22
    out = Image.new("RGBA", (cell.width + pad * 2, cell.height + pad * 2))
    mask = Image.new("L", out.size)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *out.size], radius + pad, fill=255)
    out.paste(Image.new("RGBA", out.size, "white"), mask=mask)
    inner = Image.new("L", cell.size)
    ImageDraw.Draw(inner).rounded_rectangle([0, 0, *cell.size], radius, fill=255)
    out.paste(cell, (pad, pad), inner)
    return out


def paste_with_shadow(canvas: Image.Image, im: Image.Image, xy: tuple[int, int], angle: float):
    rot = im.rotate(angle, expand=True, resample=Image.BICUBIC)
    m = 40  # room for the blur so it fades out instead of ending in a box
    alpha = Image.new("L", (rot.width + 2 * m, rot.height + 2 * m))
    alpha.paste(rot.getchannel("A").point(lambda a: int(a * 0.24)), (m, m))
    shadow = Image.new("RGBA", alpha.size, (43, 36, 31, 255))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(16)))
    x, y = xy[0] - rot.width // 2, xy[1] - rot.height // 2
    canvas.alpha_composite(shadow, (x + 4 - m, y + 14 - m))
    canvas.alpha_composite(rot, (x, y))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", type=Path, default=Path.home() / "Library/Fonts")
    ap.add_argument("--out", type=Path, default=WEB / "public/og.png")
    args = ap.parse_args()
    xbold = ImageFont.truetype(str(args.fonts / "Pretendard-ExtraBold.ttf"), 84)
    brand = ImageFont.truetype(str(args.fonts / "Pretendard-ExtraBold.ttf"), 34)
    sub = ImageFont.truetype(str(args.fonts / "Pretendard-SemiBold.ttf"), 30)

    types = {t["id"]: t for t in json.loads((WEB / "data/relationship-types.json").read_text())}
    sheet = Image.open(WEB / "public/images/types/user-relationship-sheet.png").convert("RGB")
    canvas = Image.new("RGBA", (W, H), CREAM)
    d = ImageDraw.Draw(canvas)

    # Wordmark: 러브 (cocoa) + 코드 (pink) + small heart, same as components/BrandMark.tsx
    x, y = 72, 92
    d.text((x, y), "러브", font=brand, fill=COCOA)
    x += d.textlength("러브", font=brand) + 1
    d.text((x, y), "코드", font=brand, fill=PINK)
    x += d.textlength("코드", font=brand)
    canvas.alpha_composite(heart(16, PINK), (int(x) + 2, y - 4))

    d.text((68, 190), "우리 둘은", font=xbold, fill=COCOA)
    d.text((68, 296), "어떤 커플일까?", font=xbold, fill=PINK)
    d.text((72, 430), "사주 × MBTI로 읽는 16가지 커플 유형", font=sub, fill=MUTED)

    for (cx, cy, angle, wid), tid in zip(
        [(840, 300, 9, 230), (1060, 330, -8, 230), (930, 360, -1, 250)], PICKS
    ):
        paste_with_shadow(canvas, card(sheet, types[tid]["crop"], wid), (cx, cy), angle)
    canvas.alpha_composite(heart(30, PINK), (700, 96))
    canvas.alpha_composite(heart(20, PINK), (1130, 540))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(args.out, optimize=True)
    print(args.out, args.out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()

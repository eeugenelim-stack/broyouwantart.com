#!/usr/bin/env python3
"""Build a synthetic manifest so the PDF layout can be checked without network.

Exercises every layout rule: collection overflow across pages, Last One and
Double Chance prizes, F-1/F-2 design variants, extreme image aspect ratios,
Japanese prize names, and prizes with no image at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "build-fixture")
IMAGES = OUT / "images"
IMAGES.mkdir(parents=True, exist_ok=True)

PALETTE = [(214, 69, 65), (46, 110, 186), (240, 176, 48), (76, 158, 96),
           (150, 92, 176), (58, 58, 64)]


def make_image(name: str, size: tuple[int, int], colour) -> str:
    img = Image.new("RGB", size, colour)
    d = ImageDraw.Draw(img)
    d.rectangle([6, 6, size[0] - 7, size[1] - 7], outline=(255, 255, 255), width=4)
    d.text((14, 14), f"{name}\n{size[0]}x{size[1]}", fill=(255, 255, 255))
    path = IMAGES / f"{name}.png"
    img.save(path)
    return f"images/{name}.png"


def prize(label, ja, en, img):
    return {"label": label, "name_ja": ja, "name_en": en,
            "image_url": "https://1kuji.com/assets/x.jpg",
            "image_file": img, "note": ""}


collections = []

# 1. Tall + wide mixed aspect ratios, 7 prizes => overflows onto a second page.
prizes = []
sizes = [(800, 1200), (1200, 800), (1000, 1000), (600, 1500),
         (1500, 620), (900, 1100), (1100, 900)]
for i, sz in enumerate(sizes):
    letter = chr(ord("A") + i)
    prizes.append(prize(f"Prize {letter}", f"{letter}賞 フィギュア",
                        f"Figure {letter}",
                        make_image(f"c1_{letter}", sz, PALETTE[i % len(PALETTE)])))
prizes.append(prize("Last One Prize", "ラストワン賞 特別カラーフィギュア",
                    "Special Colour Figure",
                    make_image("c1_last", (900, 1200), PALETTE[0])))
prizes.append(prize("Double Chance Prize", "ダブルチャンス賞 限定フィギュア",
                    "Limited Edition Figure",
                    make_image("c1_dc", (1000, 900), PALETTE[1])))
collections.append({
    "title": "Ichiban Kuji SAKAMOTO DAYS vol.2",
    "source_url": "https://1kuji.com/products/sakamoto-days-vol2",
    "prizes": prizes, "error": "",
})

# 2. Design variants F-1 / F-2 / F-3 plus one prize with no image.
prizes = [
    prize("Prize A", "A賞 ちいかわ 収納フィギュア", "Cozy Bathhouse Storage Figure",
          make_image("c2_A", (1100, 1000), PALETTE[2])),
    prize("Prize F-1", "F賞 ラバーチャーム", "Rubber Charm (Design 1)",
          make_image("c2_F1", (800, 800), PALETTE[3])),
    prize("Prize F-2", "F賞 ラバーチャーム", "Rubber Charm (Design 2)",
          make_image("c2_F2", (800, 800), PALETTE[4])),
    prize("Prize F-3", "F賞 ラバーチャーム", "Rubber Charm (Design 3)", ""),
]
collections.append({
    "title": "Ichiban Kuji Chiikawa ~Chiikawa's Public Bath~",
    "source_url": "https://1kuji.com/products/chiikawa-chiikawas-public-bath",
    "prizes": prizes, "error": "",
})

# 3. A page that could not be scraped at all.
collections.append({
    "title": "Ichiban Kuji Pokemon Mega Evolution",
    "source_url": "https://1kuji.com/products/pokemon-megaevolution",
    "prizes": [], "error": "HTTP 404",
})

# 4. Exactly four prizes: one full page, no overflow. Long name to test wrapping.
prizes = [
    prize("Prize A", "A賞", "An Extremely Long Prize Name That Must Wrap Across "
          "Two Caption Lines And Then Be Truncated Cleanly",
          make_image("c4_A", (1000, 1000), PALETTE[5])),
    prize("Prize B", "B賞 タオル", "Towel",
          make_image("c4_B", (1200, 700), PALETTE[0])),
    prize("Prize C", "C賞 グラス", "Glass",
          make_image("c4_C", (700, 1200), PALETTE[1])),
    prize("Prize D", "D賞 クリアファイル", "",   # falls back to the Japanese name
          make_image("c4_D", (1000, 800), PALETTE[2])),
]
collections.append({
    "title": "Ichiban Kuji One Piece - The Unbreakable Law",
    "source_url": "https://1kuji.com/products/one-piece-the-unbreakable-law",
    "prizes": prizes, "error": "",
})

(OUT / "manifest.json").write_text(
    json.dumps({"collections": collections}, ensure_ascii=False, indent=2),
    encoding="utf-8")
print(f"fixture written to {OUT}/manifest.json "
      f"({len(collections)} collections, "
      f"{sum(len(c['prizes']) for c in collections)} prizes)")

#!/usr/bin/env python3
"""Phase 2: turn a scraped manifest into `ichiban_kuji_prize_catalogue.pdf`.

Layout rules implemented here:
  * compact 2x2 grid, at most four prizes per page
  * each collection stays together; it continues on the next page when it
    overflows, and never shares a page with another collection
  * the collection title sits at the top of its first page, with the official
    source URL beneath it in small text
  * labels read `Prize A - <name>`; images keep their original proportions
  * a prize with no official image prints "Official image unavailable" and is
    listed again in a closing Missing Images section

Usage:
    python3 kuji_build_pdf.py --manifest build/manifest.json \
        --out ichiban_kuji_prize_catalogue.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MARGIN = 36
GUTTER = 18
COLS, ROWS = 2, 2

TITLE_BLOCK_H = 46      # first page of a collection
CONT_BLOCK_H = 22       # continuation pages
CAPTION_H = 30          # two caption lines under each image
CAPTION_LEADING = 11

LATIN = "Helvetica"
LATIN_BOLD = "Helvetica-Bold"
CJK = "HeiseiKakuGo-W5"     # built-in CID font, no font file needed


def register_fonts() -> str:
    """Register the CJK face so Japanese prize names don't render as blanks."""
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(CJK))
        return CJK
    except Exception:
        return LATIN


def pick_font(text: str, cjk_font: str, bold: bool = False) -> str:
    """Helvetica has no CJK glyphs; switch faces when the text needs it."""
    if any(ord(ch) > 0x2E80 for ch in text):
        return cjk_font
    return LATIN_BOLD if bold else LATIN


def wrap(text: str, font: str, size: float, max_w: float, max_lines: int) -> list[str]:
    """Greedy wrap that also breaks mid-run for unspaced CJK."""
    if not text:
        return []
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= max_w:
            current = trial
            continue
        if current:
            lines.append(current)
            current = word
        else:
            current = word
        # A single word (or CJK run) wider than the line: break it by character.
        while pdfmetrics.stringWidth(current, font, size) > max_w:
            cut = len(current)
            while cut > 1 and pdfmetrics.stringWidth(current[:cut], font, size) > max_w:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    lines = lines[:max_lines]
    # Mark truncation so nothing silently disappears.
    if lines and (len(" ".join(lines)) < len(text)):
        last = lines[-1]
        while last and pdfmetrics.stringWidth(last + "...", font, size) > max_w:
            last = last[:-1]
        lines[-1] = last + "..."
    return lines


def prize_caption(prize: dict) -> str:
    """`Prize A - <English name>`, per the required label format."""
    name = (prize.get("name_en") or "").strip() or (prize.get("name_ja") or "").strip()
    label = prize.get("label") or "Prize"
    return f"{label} - {name}" if name else label


def draw_cell(c: canvas.Canvas, prize: dict, base: Path, x: float, y: float,
              w: float, h: float, cjk: str, missing: list, collection: str) -> None:
    """Draw one prize into the box whose bottom-left corner is (x, y)."""
    img_h = h - CAPTION_H
    rel = prize.get("image_file") or ""
    path = (base / rel) if rel else None

    if path and path.is_file():
        try:
            reader = ImageReader(str(path))
            iw, ih = reader.getSize()
            scale = min(w / iw, img_h / ih)          # preserve proportions
            dw, dh = iw * scale, ih * scale
            # Bottom-align: the caption sits directly under its image, and every
            # caption in a row still shares one baseline.
            c.drawImage(reader, x + (w - dw) / 2, y + CAPTION_H,
                        width=dw, height=dh, mask="auto")
        except Exception:
            path = None
    if not (path and path.is_file()):
        missing.append((collection, prize.get("label", "?")))
        c.saveState()
        c.setDash(2, 2)
        c.setStrokeColorRGB(0.72, 0.72, 0.72)
        c.rect(x, y + CAPTION_H, w, img_h)
        c.restoreState()
        msg = "Official image unavailable"
        c.setFont(LATIN, 8.5)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawCentredString(x + w / 2, y + CAPTION_H + img_h / 2 - 3, msg)
        c.setFillColorRGB(0, 0, 0)

    caption = prize_caption(prize)
    font = pick_font(caption, cjk, bold=True)
    lines = wrap(caption, font, 8.5, w, 2)
    c.setFont(font, 8.5)
    ty = y + CAPTION_H - 12
    for line in lines:
        c.drawString(x, ty, line)
        ty -= CAPTION_LEADING


def draw_header(c: canvas.Canvas, title: str, url: str, first: bool,
                cjk: str) -> float:
    """Draw the collection header; return the y of the grid's top edge."""
    top = PAGE_H - MARGIN
    if first:
        font = pick_font(title, cjk, bold=True)
        c.setFont(font, 14)
        for line in wrap(title, font, 14, PAGE_W - 2 * MARGIN, 1):
            c.drawString(MARGIN, top - 13, line)
        c.setFont(LATIN, 6.8)
        c.setFillColorRGB(0.42, 0.42, 0.42)
        c.drawString(MARGIN, top - 24, url)
        c.setFillColorRGB(0, 0, 0)
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.82, 0.82, 0.82)
        c.line(MARGIN, top - 31, PAGE_W - MARGIN, top - 31)
        c.setStrokeColorRGB(0, 0, 0)
        return top - TITLE_BLOCK_H
    font = pick_font(title, cjk)
    c.setFont(font, 8)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    for line in wrap(f"{title} (continued)", font, 8, PAGE_W - 2 * MARGIN, 1):
        c.drawString(MARGIN, top - 9, line)
    c.setFillColorRGB(0, 0, 0)
    return top - CONT_BLOCK_H


def draw_footer(c: canvas.Canvas, page_no: int) -> None:
    c.setFont(LATIN, 7)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    c.drawCentredString(PAGE_W / 2, MARGIN / 2 + 2, str(page_no))
    c.setFillColorRGB(0, 0, 0)


def build(manifest_path: Path, out_path: Path) -> dict:
    cjk = register_fonts()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    collections = data.get("collections", [])
    base = manifest_path.parent

    c = canvas.Canvas(str(out_path), pagesize=A4)
    c.setTitle("Ichiban Kuji Prize Catalogue")
    missing: list[tuple[str, str]] = []
    page_no = 0
    prize_total = 0

    for coll in collections:
        prizes = coll.get("prizes") or []
        title = coll.get("title") or "(untitled collection)"
        url = coll.get("source_url", "")
        prize_total += len(prizes)

        # A page with nothing on it still records the collection and its problem.
        chunks = [prizes[i:i + COLS * ROWS] for i in range(0, len(prizes), COLS * ROWS)] \
            or [[]]

        for page_idx, chunk in enumerate(chunks):
            page_no += 1
            grid_top = draw_header(c, title, url, page_idx == 0, cjk)
            grid_h = grid_top - MARGIN
            cell_w = (PAGE_W - 2 * MARGIN - GUTTER) / COLS
            cell_h = (grid_h - GUTTER) / ROWS

            if not chunk:
                note = coll.get("error") or "No official prize images found."
                c.setFont(LATIN, 9)
                c.setFillColorRGB(0.45, 0.45, 0.45)
                c.drawString(MARGIN, grid_top - 16, f"Official image unavailable - {note}")
                c.setFillColorRGB(0, 0, 0)
                missing.append((title, "entire collection"))
            for slot, prize in enumerate(chunk):
                col, row = slot % COLS, slot // COLS
                x = MARGIN + col * (cell_w + GUTTER)
                y = grid_top - (row + 1) * cell_h - row * GUTTER
                draw_cell(c, prize, base, x, y, cell_w, cell_h, cjk, missing, title)

            draw_footer(c, page_no)
            c.showPage()

    # --- Missing Images section (requirement 12) ---
    if missing:
        page_no += 1
        c.setFont(LATIN_BOLD, 14)
        c.drawString(MARGIN, PAGE_H - MARGIN - 13, "Missing Images")
        c.setFont(LATIN, 8)
        c.setFillColorRGB(0.42, 0.42, 0.42)
        c.drawString(MARGIN, PAGE_H - MARGIN - 25,
                     f"{len(missing)} entries had no official image available.")
        c.setFillColorRGB(0, 0, 0)
        y = PAGE_H - MARGIN - 46
        for coll_title, label in missing:
            if y < MARGIN + 20:
                draw_footer(c, page_no)
                c.showPage()
                page_no += 1
                y = PAGE_H - MARGIN - 13
            line = f"{coll_title} - {label}"
            font = pick_font(line, cjk)
            c.setFont(font, 8.5)
            for part in wrap(line, font, 8.5, PAGE_W - 2 * MARGIN, 1):
                c.drawString(MARGIN, y, part)
            y -= 13
        draw_footer(c, page_no)
        c.showPage()

    c.save()
    return {
        "collections": len(collections),
        "prizes": prize_total,
        "missing": len(missing),
        "missing_list": missing,
        "pages": page_no,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default="build/manifest.json")
    ap.add_argument("--out", default="ichiban_kuji_prize_catalogue.pdf")
    args = ap.parse_args()

    stats = build(Path(args.manifest), Path(args.out))
    print(f"Wrote {args.out}")
    print(f"  Collections processed : {stats['collections']}")
    print(f"  Total prizes          : {stats['prizes']}")
    print(f"  Missing images        : {stats['missing']}")
    print(f"  Pages                 : {stats['pages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

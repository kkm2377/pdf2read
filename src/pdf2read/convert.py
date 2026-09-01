from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Callable

import pymupdf

from pdf2read.layout import detect_columns, running_headers
from pdf2read.outline import units_by_chunks, units_from_outline, units_from_visual_titles
from pdf2read.render import UI, write_book
from pdf2read.theme import extract_theme

Progress = Callable[[str], None]


def detect_language(doc, start: int, end: int) -> str:
    """Guess html lang from scripts in the first pages. Chrome uses this as source."""
    sample = []
    last = min(end, start + 7)
    for pn in range(start, last + 1):
        sample.append(doc[pn - 1].get_text("text") or "")
        if sum(len(s) for s in sample) > 5000:
            break
    text = "".join(sample)
    kana = len(re.findall(r"[\u3040-\u30ff]", text))
    hangul = len(re.findall(r"[\uac00-\ud7af]", text))
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if kana >= 6:
        return "ja"
    if hangul >= 12:
        return "ko"
    if han >= 24 and kana < 3:
        return "zh"
    if latin >= 40:
        return "en"
    return "ja"


def book_id(pdf: Path, title: str) -> str:
    raw = f"{pdf.resolve()}::{title}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def plan_units(doc, start: int, end: int, chunk: int, log: Progress):
    toc = doc.get_toc(simple=True)
    units = units_from_outline(toc, doc.page_count, start, end)
    mode = "outline"
    if not units:
        units = units_from_visual_titles(doc, start, end)
        mode = "visual"
        if units:
            log(f"No PDF outline; split on {len(units)} large titles.")
        else:
            units = units_by_chunks(doc.page_count, start, end, chunk)
            mode = "chunks"
            log(f"No PDF outline; grouping every {chunk} pages.")
    return units, mode


def convert_book(
    pdf: str | Path,
    out: str | Path,
    *,
    lang: str = "auto",
    ui_lang: str = "ko",
    start: int | None = None,
    end: int | None = None,
    chunk: int = 8,
    show_library: bool = False,
    progress: Progress | None = None,
) -> dict:
    """Convert a selectable-text PDF into an HTML viewer folder.

    Returns a dict with title, pages, units, out, mode, layout.
    """
    log = progress or (lambda _m: None)
    pdf_path = Path(pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    out_path = Path(out).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    for old in out_path.glob("*.html"):
        old.unlink()
    assets = out_path / "assets"
    if assets.exists():
        shutil.rmtree(assets)

    doc = pymupdf.open(pdf_path)
    try:
        title = (doc.metadata or {}).get("title") or pdf_path.stem
        title = str(title).strip() or pdf_path.stem
        a = max(1, start or 1)
        b = min(doc.page_count, end or doc.page_count)
        units, mode = plan_units(doc, a, b, chunk, log)
        starts = [u.start for u in units] or [a]
        if len(starts) <= 12:
            sample = starts
        else:
            sample = starts[:2] + starts[len(starts)//4:len(starts)//4 + 4] + starts[len(starts)//2:len(starts)//2 + 4] + starts[-3:]
        if not lang or lang == "auto":
            lang = detect_language(doc, a, b)
            log(f"  detected lang={lang}")
        layout = detect_columns(doc, sample)
        pages = []
        for u in units:
            pages.extend(u.pdf_pages)
        headers = running_headers(doc, pages, layout)
        theme = extract_theme(doc, sample)
        ui = dict(UI.get(ui_lang, UI["ko"]))
        ui["_lang"] = ui_lang
        ui["show_library"] = show_library
        book = {"id": book_id(pdf_path, title), "title": title, "source": str(pdf_path)}
        log(f"Convert {pdf_path.name}")
        log(f"  pages {a}–{b}  units {len(units)}  toc={mode}  columns={layout['mode']}")
        log(f"  accent {theme['accent']}  split_x={layout['split_x']:.1f}")
        write_book(out_path, book, units, doc, layout, headers, theme, ui, lang, progress=log)
        log(f"Wrote {out_path}")
        return {
            "id": book["id"],
            "title": title,
            "pages": b - a + 1,
            "units": len(units),
            "out": str(out_path),
            "mode": mode,
            "layout": layout["mode"],
            "accent": theme["accent"],
        }
    finally:
        doc.close()

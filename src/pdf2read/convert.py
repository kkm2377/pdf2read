from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from typing import Callable

import pymupdf

from pdf2read.layout import detect_columns, running_headers
from pdf2read.outline import units_by_chunks, units_from_outline, units_from_visual_titles
from pdf2read.pipeline import create_pipeline
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
    return "und"


def book_id(pdf: Path, title: str) -> str:
    raw = f"{pdf.resolve()}::{title}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def _publish_output(staging: Path, destination: Path) -> None:
    backup = None
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"output path is not a directory: {destination}")
        backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex[:8]}"
        destination.rename(backup)
    try:
        staging.rename(destination)
    except Exception:
        if backup is not None and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


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
    profile: str = "balanced",
    ocr: str = "auto",
    ocr_languages: str = "eng+jpn+kor",
    page_images: str = "auto",
    confidence_threshold: float = 0.62,
    cache: bool = True,
    max_engine_pages: int | None = 80,
    progress: Progress | None = None,
) -> dict:
    """Convert a selectable-text PDF into an HTML viewer folder.

    Returns a dict with title, pages, units, out, mode, layout.
    """
    log = progress or (lambda _m: None)
    if profile not in {"auto", "fast", "balanced"}:
        raise ValueError("profile must be 'auto', 'fast', or 'balanced'")
    if ocr not in {"auto", "off", "ocrmypdf"}:
        raise ValueError("ocr must be 'auto', 'off', or 'ocrmypdf'")
    if page_images not in {"auto", "always", "never"}:
        raise ValueError("page_images must be 'auto', 'always', or 'never'")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    pdf_path = Path(pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    out_path = Path(out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(mkdtemp(prefix=f".{out_path.name}.build-", dir=out_path.parent))

    working_pdf = pdf_path
    ocr_temp = None
    ocr_preprocessed = False
    if ocr == "ocrmypdf":
        from pdf2read.engines.ocr import preprocess_with_ocrmypdf

        ocr_temp = TemporaryDirectory(prefix="pdf2read-ocr-")
        candidate = Path(ocr_temp.name) / "ocr.pdf"
        ocr_preprocessed = preprocess_with_ocrmypdf(
            pdf_path,
            candidate,
            languages=ocr_languages,
            log=log,
        )
        if ocr_preprocessed:
            working_pdf = candidate
    try:
        doc = pymupdf.open(working_pdf)
    except Exception:
        if ocr_temp is not None:
            ocr_temp.cleanup()
        shutil.rmtree(staging, ignore_errors=True)
        raise
    try:
        if doc.needs_pass:
            raise ValueError("암호화된 PDF입니다. 암호를 해제한 사본을 사용해 주세요.")
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
        pipeline = create_pipeline(
            doc,
            working_pdf,
            pages,
            profile=profile,
            ocr="off" if ocr_preprocessed else ("auto" if ocr == "ocrmypdf" else ocr),
            source_lang=lang,
            page_images=page_images,
            confidence_threshold=confidence_threshold,
            cache=cache,
            max_engine_pages=max_engine_pages,
            source_label=ui["source_page"],
            log=log,
        )
        write_book(
            staging,
            book,
            units,
            doc,
            layout,
            headers,
            theme,
            ui,
            lang,
            pipeline=pipeline,
            progress=log,
        )
        _publish_output(staging, out_path)
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
            "pipeline": profile,
            "ocr_preprocessed": ocr_preprocessed,
            **pipeline.stats.to_dict(),
        }
    finally:
        doc.close()
        if ocr_temp is not None:
            ocr_temp.cleanup()
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

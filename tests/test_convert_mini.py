from pathlib import Path

import pymupdf

from pdf2read.convert import convert_book


def test_convert_mini_pdf(tmp_path: Path):
    pdf = tmp_path / "mini.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text((50, 72), "Sample Chapter", fontsize=22)
    page.insert_text((50, 120), "This is a short selectable-text PDF for pdf2read.", fontsize=11)
    page.insert_text((50, 150), "The next sentence should stay as HTML.", fontsize=11)
    doc.set_toc([(1, "Sample Chapter", 1)])
    doc.save(pdf)
    doc.close()

    out = tmp_path / "book"
    result = convert_book(pdf, out, lang="en", ui_lang="en")
    assert result["units"] >= 1
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Sample Chapter" in html
    assert (out / "viewer" / "viewer.css").exists()
    unit = next(p for p in out.glob("*.html") if p.name != "index.html")
    body = unit.read_text(encoding="utf-8")
    assert "selectable-text PDF" in body


def test_detect_language_english(tmp_path: Path):
    from pdf2read.convert import detect_language

    pdf = tmp_path / "en.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "The quick brown fox jumps over the lazy dog again and again.",
        fontsize=12,
    )
    doc.save(pdf)
    doc.close()
    opened = pymupdf.open(pdf)
    assert detect_language(opened, 1, 1) == "en"
    opened.close()

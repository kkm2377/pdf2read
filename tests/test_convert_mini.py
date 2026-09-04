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


def test_detect_language_unknown_for_image_only_pdf(tmp_path: Path):
    from pdf2read.convert import detect_language

    source = pymupdf.open()
    page = source.new_page()
    page.insert_text((50, 72), "Pixels only", fontsize=12)
    pixmap = page.get_pixmap()
    doc = pymupdf.open()
    target = doc.new_page()
    target.insert_image(target.rect, pixmap=pixmap)
    opened = doc
    assert detect_language(opened, 1, 1) == "und"
    opened.close()
    source.close()


def test_failed_conversion_preserves_existing_output(tmp_path: Path):
    encrypted = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "secret", fontsize=12)
    doc.save(
        encrypted,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="reader",
    )
    doc.close()

    out = tmp_path / "book"
    out.mkdir()
    (out / "index.html").write_text("keep me", encoding="utf-8")
    try:
        convert_book(encrypted, out, profile="fast")
    except ValueError:
        pass
    assert (out / "index.html").read_text(encoding="utf-8") == "keep me"
    assert not list(tmp_path.glob(".book.build-*"))


def test_successful_conversion_atomically_replaces_existing_output(tmp_path: Path):
    pdf = tmp_path / "new.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "New readable content", fontsize=12)
    doc.set_toc([(1, "New chapter", 1)])
    doc.save(pdf)
    doc.close()

    out = tmp_path / "book"
    out.mkdir()
    (out / "obsolete.txt").write_text("old", encoding="utf-8")
    convert_book(pdf, out, profile="fast", page_images="never")
    assert not (out / "obsolete.txt").exists()
    assert "New chapter" in (out / "index.html").read_text(encoding="utf-8")
    assert not list(tmp_path.glob(".book.backup-*"))

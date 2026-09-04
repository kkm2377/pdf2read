import json
from pathlib import Path

import pymupdf

from pdf2read.convert import convert_book


def _image_only_pdf(path: Path):
    source = pymupdf.open()
    page = source.new_page(width=420, height=595)
    page.insert_text((50, 100), "Scanned page text visible only as pixels.", fontsize=16)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
    scanned = pymupdf.open()
    out_page = scanned.new_page(width=420, height=595)
    out_page.insert_image(out_page.rect, pixmap=pixmap)
    scanned.save(path)
    scanned.close()
    source.close()


def test_low_confidence_scan_gets_original_page_fallback(tmp_path: Path):
    pdf = tmp_path / "scan.pdf"
    _image_only_pdf(pdf)
    out = tmp_path / "book"
    result = convert_book(pdf, out, profile="fast", page_images="auto")

    unit = next(path for path in out.glob("*.html") if path.name != "index.html")
    html = unit.read_text(encoding="utf-8")
    images = list((out / "assets" / "pages").glob("p00001.*"))
    quality = json.loads((out / "viewer" / "quality.json").read_text(encoding="utf-8"))

    assert images
    assert 'class="source-page" data-source-page="1" open' in html
    assert 'class="diagram"' not in html
    assert "원본 페이지 보기" in html
    assert result["image_pages"] == 1
    assert quality["pages"][0]["source_image"].startswith("assets/pages/")


def test_page_image_fallback_can_be_disabled(tmp_path: Path):
    pdf = tmp_path / "scan.pdf"
    _image_only_pdf(pdf)
    out = tmp_path / "book"
    result = convert_book(
        pdf,
        out,
        profile="fast",
        page_images="never",
    )
    assert result["image_pages"] == 0
    assert not (out / "assets" / "pages").exists()
    quality = json.loads((out / "viewer" / "quality.json").read_text(encoding="utf-8"))
    assert quality["pages"][0]["route"] == "rules"
    assert "source_image_disabled" in quality["pages"][0]["reasons"]

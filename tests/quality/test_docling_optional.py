from pathlib import Path

import pymupdf
import pytest

from pdf2read.convert import convert_book
from pdf2read.engines import DoclingEngine, docling_available
from tests.fixtures.builders import build_scan_pdf


@pytest.mark.needs_model
@pytest.mark.skipif(not docling_available(), reason="Docling quality extra is not installed")
def test_docling_ocr_processes_scanned_page(tmp_path: Path):
    pdf = build_scan_pdf(tmp_path / "scan.pdf")
    out = tmp_path / "out"
    result = convert_book(
        pdf,
        out,
        lang="en",
        profile="balanced",
        ocr="auto",
        page_images="auto",
        max_engine_pages=2,
    )
    html = "\n".join(path.read_text(encoding="utf-8") for path in out.glob("*.html"))
    assert result["engine_pages"] == 1
    assert result["image_pages"] == 1
    assert 'class="docling-page"' in html
    assert 'class="source-page"' in html
    assert "Scanned" in html or result["image_pages"] == 1


@pytest.mark.needs_model
@pytest.mark.skipif(not docling_available(), reason="Docling quality extra is not installed")
def test_docling_embeds_picture_images(tmp_path: Path):
    picture_doc = pymupdf.open()
    picture_page = picture_doc.new_page(width=120, height=90)
    picture_page.draw_rect((10, 10, 110, 80), color=(0.8, 0.2, 0.1), fill=(0.95, 0.8, 0.6))
    picture_page.insert_text((30, 50), "PICTURE", fontsize=12)
    pixmap = picture_page.get_pixmap()
    picture_doc.close()

    pdf = tmp_path / "picture.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text((42, 70), "Document with an embedded picture", fontsize=15)
    page.insert_text((42, 110), "Text before the picture remains available.", fontsize=10)
    page.insert_image((100, 150, 320, 315), pixmap=pixmap)
    page.insert_text((42, 350), "Text after the picture remains available.", fontsize=10)
    doc.save(pdf)
    doc.close()

    result = DoclingEngine(ocr="off", source_lang="en").extract_page(pdf, 1)
    assert "data:image" in result.main_html

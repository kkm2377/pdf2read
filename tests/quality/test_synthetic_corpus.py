from pathlib import Path

import pymupdf
import pytest

from pdf2read.convert import convert_book
from tests.fixtures.builders import (
    build_corrupt_pdf,
    build_encrypted_pdf,
    build_exam_pdf,
    build_figure_wrap_pdf,
    build_math_pdf,
    build_mixed_pdf,
    build_selectable_pdf,
    build_table_pdf,
    build_two_column_pdf,
    build_two_up_pdf,
    build_vertical_pdf,
)
from tests.quality.harness import appears_in_order, audit_output, ngram_recall


def _convert(builder, tmp_path: Path, **options):
    pdf = builder(tmp_path / "source.pdf")
    out = tmp_path / "out"
    result = convert_book(
        pdf,
        out,
        profile="fast",
        page_images="auto",
        **options,
    )
    return pdf, out, result


def _pdf_text(pdf: Path) -> str:
    doc = pymupdf.open(pdf)
    try:
        return "".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


@pytest.mark.parametrize(
    ("builder", "minimum_recall"),
    [
        (build_selectable_pdf, 0.82),
        (build_two_column_pdf, 0.72),
        (build_two_up_pdf, 0.72),
        (build_math_pdf, 0.8),
        (build_figure_wrap_pdf, 0.7),
    ],
)
def test_selectable_corpus_recall_and_integrity(builder, minimum_recall, tmp_path: Path):
    pdf, out, _result = _convert(builder, tmp_path)
    audit = audit_output(out)
    assert ngram_recall(_pdf_text(pdf), audit["text"]) >= minimum_recall
    assert audit["missing_refs"] == []
    assert all(audit["languages"])
    assert audit["images"] == audit["images_with_alt"]


def test_two_up_reading_order(tmp_path: Path):
    _pdf, out, _result = _convert(build_two_up_pdf, tmp_path)
    text = audit_output(out)["text"]
    assert appears_in_order(text, ["Left item 0", "Left item 15", "Right item 0", "Right item 15"])


def test_table_becomes_html_table(tmp_path: Path):
    _pdf, out, _result = _convert(build_table_pdf, tmp_path)
    html = "\n".join(path.read_text(encoding="utf-8") for path in out.glob("*.html"))
    assert '<table class="book-table">' in html
    assert all(value in html for value in ("Alpha", "Beta", "Closed"))


def test_exam_becomes_question_and_choices(tmp_path: Path):
    _pdf, out, _result = _convert(build_exam_pdf, tmp_path)
    html = "\n".join(path.read_text(encoding="utf-8") for path in out.glob("*.html"))
    assert "<article class='q-card'>" in html
    assert "<ul class='choices'>" in html
    assert html.count("<span class='mark'>") == 4


def test_vertical_page_gets_original_fallback(tmp_path: Path):
    _pdf, out, result = _convert(build_vertical_pdf, tmp_path)
    html = "\n".join(path.read_text(encoding="utf-8") for path in out.glob("*.html"))
    assert result["image_pages"] == 1
    assert 'class="source-page"' in html


def test_mixed_document_only_falls_back_for_scan(tmp_path: Path):
    _pdf, out, result = _convert(build_mixed_pdf, tmp_path)
    quality = (out / "viewer" / "quality.json").read_text(encoding="utf-8")
    assert result["pages"] == 2
    assert result["image_pages"] == 1
    assert '"page": 2' in quality
    assert '"source_image"' in quality


def test_encrypted_pdf_has_clear_error(tmp_path: Path):
    pdf = build_encrypted_pdf(tmp_path / "encrypted.pdf")
    with pytest.raises(ValueError, match="암호화된 PDF"):
        convert_book(pdf, tmp_path / "out", profile="fast")


def test_corrupt_pdf_fails_instead_of_writing_partial_book(tmp_path: Path):
    pdf = build_corrupt_pdf(tmp_path / "corrupt.pdf")
    with pytest.raises(Exception):
        convert_book(pdf, tmp_path / "out", profile="fast")

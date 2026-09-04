from pathlib import Path

import pytest

from pdf2read.convert import convert_book
from tests.fixtures.builders import build_large_pdf
from tests.quality.harness import audit_output


@pytest.mark.slow
def test_large_synthetic_document_completes_with_valid_links(tmp_path: Path):
    pdf = build_large_pdf(tmp_path / "large.pdf", pages=120)
    out = tmp_path / "out"
    result = convert_book(
        pdf,
        out,
        profile="fast",
        page_images="never",
    )
    audit = audit_output(out)
    assert result["pages"] == 120
    assert result["units"] >= 10
    assert audit["missing_refs"] == []
    assert "Page 120 line 7" in audit["text"]

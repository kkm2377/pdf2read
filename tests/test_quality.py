import pymupdf

from pdf2read.quality import score_page


def _text_page():
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    for i in range(14):
        page.insert_text(
            (42, 60 + i * 24),
            f"Readable selectable text line {i} for a normal document page.",
            fontsize=10,
        )
    return doc, page


def _scanned_page():
    source, source_page = _text_page()
    pixmap = source_page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=595)
    page.insert_image(page.rect, pixmap=pixmap)
    source.close()
    return doc, page


def test_selectable_text_page_uses_fast_rules():
    doc, page = _text_page()
    try:
        score = score_page(page, 1, engine_available=True)
        assert score.confidence >= 0.8
        assert score.route == "rules"
        assert score.metrics.chars > 100
    finally:
        doc.close()


def test_scanned_page_routes_to_docling_when_available():
    doc, page = _scanned_page()
    try:
        score = score_page(page, 1, engine_available=True)
        assert score.confidence < 0.2
        assert score.route == "docling"
        assert "scanned" in score.reasons
    finally:
        doc.close()


def test_scanned_page_routes_to_source_image_without_engine():
    doc, page = _scanned_page()
    try:
        score = score_page(page, 1, engine_available=False)
        assert score.route == "source-image"
        data = score.to_dict()
        assert data["metrics"]["images"] == 1
        assert data["confidence"] == score.confidence
    finally:
        doc.close()


def test_few_rotated_diagram_labels_do_not_route_whole_page():
    doc, page = _text_page()
    try:
        for i in range(4):
            page.insert_text((300 + i * 18, 500), f"Axis {i}", fontsize=8, rotate=90)
        score = score_page(page, 1, engine_available=True)
        assert score.route == "rules"
        assert "rotated_text" not in score.reasons
    finally:
        doc.close()

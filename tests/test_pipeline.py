from pathlib import Path

import pymupdf

from pdf2read.cache import PageCache
from pdf2read.engines.docling_engine import DoclingEngine, _html_fragment, _ngram_recall
from pdf2read.model import EnginePage
from pdf2read.pipeline import PipelineContext, create_pipeline
from pdf2read.quality import score_page


class FakeEngine:
    name = "docling"
    version = "test"

    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def extract_page(self, _source: Path, page_number: int) -> EnginePage:
        if self.fail:
            raise RuntimeError("model failed")
        return EnginePage(
            page=page_number,
            main_html="<p>OCR result</p>",
            confidence=0.9,
            engine=self.name,
        )


def _scan_pdf(path: Path):
    source = pymupdf.open()
    text_page = source.new_page(width=300, height=400)
    text_page.insert_text((30, 50), "scan source text " * 10, fontsize=12)
    pixmap = text_page.get_pixmap()
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=400)
    page.insert_image(page.rect, pixmap=pixmap)
    doc.save(path)
    doc.close()
    source.close()


def test_pipeline_routes_scan_to_source_without_docling(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scan_pdf(pdf)
    doc = pymupdf.open(pdf)
    monkeypatch.setattr("pdf2read.pipeline.docling_available", lambda: False)
    try:
        context = create_pipeline(doc, pdf, [1], profile="balanced", cache=False)
        assert context.engine is None
        assert context.scores[1].route == "source-image"
        assert context.wants_source_image(1)
    finally:
        doc.close()


def test_pipeline_engine_success_and_failure(tmp_path: Path):
    source = tmp_path / "source.pdf"
    _scan_pdf(source)
    doc = pymupdf.open(source)
    score = score_page(doc[0], 1, engine_available=True)
    doc.close()

    success = PipelineContext(
        source=source,
        profile="balanced",
        ocr="auto",
        source_lang="en",
        page_images="auto",
        confidence_threshold=0.62,
        scores={1: score},
        engine=FakeEngine(),
    )
    result = success.extract_with_engine(1)
    assert result and result.main_html == "<p>OCR result</p>"
    assert success.stats.engine_pages == 1
    assert success.scores[1].engine_confidence == 0.9
    assert success.scores[1].confidence < 0.2
    assert success.wants_source_image(1, result)
    assert "resolved_by_docling" in success.scores[1].reasons
    low_recall = EnginePage(
        page=1,
        main_html="<p>partial</p>",
        confidence=0.8,
        engine="docling",
        reasons=["low_text_recall"],
    )
    assert success.wants_source_image(1, low_recall)

    score.route = "docling"
    failure = PipelineContext(
        source=source,
        profile="balanced",
        ocr="auto",
        source_lang="en",
        page_images="auto",
        confidence_threshold=0.62,
        scores={1: score},
        engine=FakeEngine(fail=True),
    )
    assert failure.extract_with_engine(1) is None
    assert failure.stats.engine_errors == 1
    assert failure.scores[1].route == "source-image"


def test_page_cache_round_trip(tmp_path: Path):
    source = tmp_path / "source.pdf"
    _scan_pdf(source)
    cache = PageCache(source, root=tmp_path / "cache")
    page = EnginePage(
        page=1,
        main_html="<p>cached</p>",
        confidence=0.88,
        engine="docling",
        reasons=["test"],
    )
    cache.store(page, "1.0", {"ocr": "auto"})
    loaded = cache.load(1, "docling", "1.0", {"ocr": "auto"})
    assert loaded is not None
    assert loaded.main_html == "<p>cached</p>"
    assert loaded.cache_hit


def test_docling_html_fragment_drops_active_content():
    html = (
        "<html><body><p onclick=\"bad()\">Safe\x07</p>"
        "<script>alert(1)</script><iframe src='bad'></iframe></body></html>"
    )
    fragment = _html_fragment(html)
    assert fragment == "<p>Safe</p>"


def test_docling_selects_detected_ocr_language():
    japanese = DoclingEngine(source_lang="ja")
    korean = DoclingEngine(source_lang="ko")
    unknown = DoclingEngine(source_lang="und")
    assert japanese._mac_languages() == ["ja-JP", "en-US"]
    assert japanese._rapid_language() == "japan"
    assert korean._mac_languages() == ["ko-KR", "en-US"]
    assert korean._rapid_language() == "korean"
    assert unknown._mac_languages() == ["ja-JP", "ko-KR", "en-US", "zh-Hans"]
    assert unknown._rapid_language() is None


def test_docling_cache_options_include_actual_backend():
    engine = DoclingEngine(source_lang="ja")
    engine._ocr_backend = "ocrmac"
    mac_options = engine.options
    engine._ocr_backend = "rapidocr"
    rapid_options = engine.options
    assert mac_options["ocr_backend"] == "ocrmac"
    assert rapid_options["ocr_backend"] == "rapidocr"
    assert mac_options != rapid_options


def test_docling_text_recall_detects_missing_content():
    expected = "The document keeps this sentence in order. " * 8
    complete = f"<p>{expected}</p>"
    partial = "<p>The document keeps this sentence.</p>"
    assert (_ngram_recall(expected, complete) or 0) > 0.95
    assert (_ngram_recall(expected, partial) or 0) < 0.5

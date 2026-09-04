from __future__ import annotations

import importlib.metadata
import importlib.util
import html as html_lib
import re
import sys
from collections import Counter
from pathlib import Path

from pdf2read.cache import PageCache
from pdf2read.model import EnginePage


def docling_available() -> bool:
    try:
        import docling.document_converter  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def _version() -> str:
    for package in ("docling-slim", "docling"):
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "unknown"


def _html_fragment(value: str) -> str:
    match = re.search(r"<body[^>]*>(.*)</body>", value, flags=re.I | re.S)
    fragment = (match.group(1) if match else value).strip()
    fragment = re.sub(
        r"<(script|iframe|object|embed)\b[^>]*>.*?</\1\s*>",
        "",
        fragment,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"\son[a-z]+\s*=\s*(['\"]).*?\1", "", fragment, flags=re.I | re.S)
    fragment = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", fragment)
    return fragment


def _plain_length(value: str) -> int:
    text = re.sub(r"<[^>]+>", " ", value)
    return len(re.sub(r"\s+", "", text))


def _normalize_text(value: str) -> str:
    value = html_lib.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


def _ngram_recall(expected: str, actual_html: str, size: int = 3) -> float | None:
    expected_text = _normalize_text(expected)
    actual_text = _normalize_text(actual_html)
    if len(expected_text) < 80:
        return None
    wanted = Counter(
        expected_text[index:index + size]
        for index in range(len(expected_text) - size + 1)
    )
    actual = Counter(
        actual_text[index:index + size]
        for index in range(max(0, len(actual_text) - size + 1))
    )
    matched = sum(min(count, actual[token]) for token, count in wanted.items())
    return matched / max(1, sum(wanted.values()))


class DoclingEngine:
    name = "docling"

    def __init__(
        self,
        *,
        ocr: str = "auto",
        source_lang: str = "en",
        cache: PageCache | None = None,
        log=None,
    ):
        self.ocr = ocr
        self.source_lang = source_lang
        self.cache = cache
        self.log = log or (lambda _message: None)
        self.version = _version()
        self._converter = None
        self._ocr_backend = "off" if ocr == "off" else "auto"

    @property
    def options(self) -> dict:
        return {
            "ocr": self.ocr,
            "source_lang": self.source_lang,
            "platform": sys.platform,
            "ocr_backend": self._ocr_backend,
            "embedded_images": True,
        }

    def _mac_languages(self) -> list[str]:
        if self.source_lang == "und":
            return ["ja-JP", "ko-KR", "en-US", "zh-Hans"]
        primary = {
            "ja": "ja-JP",
            "ko": "ko-KR",
            "zh": "zh-Hans",
            "en": "en-US",
        }.get(self.source_lang, "en-US")
        return [primary] if primary == "en-US" else [primary, "en-US"]

    def _rapid_language(self) -> str | None:
        if self.source_lang == "und":
            return None
        return {
            "ja": "japan",
            "ko": "korean",
            "zh": "ch",
            "en": "en",
        }.get(self.source_lang, "en")

    def _build_converter(self):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_table_structure = True
        options.generate_picture_images = True
        options.do_ocr = self.ocr != "off"
        if options.do_ocr:
            if sys.platform == "darwin" and importlib.util.find_spec("ocrmac") is not None:
                try:
                    from docling.datamodel.pipeline_options import OcrMacOptions

                    options.ocr_options = OcrMacOptions(lang=self._mac_languages())
                    self._ocr_backend = "ocrmac"
                except (ImportError, RuntimeError):
                    self._set_rapid_ocr(options)
            else:
                self._set_rapid_ocr(options)
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            }
        )

    def _set_rapid_ocr(self, options) -> None:
        try:
            from docling.datamodel.pipeline_options import RapidOcrOptions

            language = self._rapid_language()
            if language is None:
                raise ValueError(
                    "RapidOCR cannot detect the language of an image-only PDF. "
                    "Choose --lang ja, ko, en, or zh."
                )
            options.ocr_options = RapidOcrOptions(lang=[language])
            self._ocr_backend = "rapidocr"
        except ImportError:
            self._ocr_backend = "docling-default"

    def extract_page(self, source: Path, page_number: int) -> EnginePage:
        if self._converter is None:
            self.log("Docling 모델을 준비합니다. 첫 실행은 시간이 걸릴 수 있습니다.")
            self._converter = self._build_converter()
        if self.cache:
            cached = self.cache.load(
                page_number,
                self.name,
                self.version,
                self.options,
            )
            if cached:
                return cached
        result = self._converter.convert(source, page_range=(page_number, page_number))
        from docling_core.types.doc import ImageRefMode

        html = _html_fragment(
            result.document.export_to_html(image_mode=ImageRefMode.EMBEDDED)
        )
        length = _plain_length(html)
        confidence = min(0.96, 0.6 + min(0.36, length / 1800))
        reasons: list[str] = []
        try:
            import pymupdf

            with pymupdf.open(source) as source_doc:
                reference = source_doc[page_number - 1].get_text("text") or ""
            recall = _ngram_recall(reference, html)
            if recall is not None:
                confidence = min(confidence, 0.35 + 0.65 * recall)
                if recall < 0.72:
                    reasons.append("low_text_recall")
        except (OSError, RuntimeError, ValueError, IndexError):
            pass
        page = EnginePage(
            page=page_number,
            main_html=f'<section class="docling-page" data-source-page="{page_number}">{html}</section>',
            confidence=confidence if length else 0.0,
            engine=self.name,
            reasons=reasons if length else ["empty_engine_output"],
        )
        if self.cache:
            self.cache.store(page, self.version, self.options)
        return page

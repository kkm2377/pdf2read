from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pdf2read.cache import PageCache
from pdf2read.engines import DoclingEngine, docling_available
from pdf2read.model import EnginePage, PageScore
from pdf2read.quality import score_pages


@dataclass
class PipelineStats:
    rules_pages: int = 0
    engine_pages: int = 0
    image_pages: int = 0
    cache_hits: int = 0
    engine_errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "rules_pages": self.rules_pages,
            "engine_pages": self.engine_pages,
            "image_pages": self.image_pages,
            "cache_hits": self.cache_hits,
            "engine_errors": self.engine_errors,
        }


@dataclass
class PipelineContext:
    source: Path
    profile: str
    ocr: str
    source_lang: str
    page_images: str
    confidence_threshold: float
    scores: dict[int, PageScore]
    engine: DoclingEngine | None = None
    log: Callable[[str], None] = lambda _message: None
    source_label: str = "원본 페이지 보기"
    stats: PipelineStats = field(default_factory=PipelineStats)
    page_results: dict[int, EnginePage] = field(default_factory=dict)
    source_images: dict[int, str] = field(default_factory=dict)

    def extract_with_engine(self, page_number: int) -> EnginePage | None:
        score = self.scores.get(page_number)
        if not score or score.route != "docling" or self.engine is None:
            return None
        try:
            result = self.engine.extract_page(self.source, page_number)
            self.page_results[page_number] = result
            score.engine_confidence = result.confidence
            if "resolved_by_docling" not in score.reasons:
                score.reasons.append("resolved_by_docling")
            for reason in result.reasons:
                if reason not in score.reasons:
                    score.reasons.append(reason)
            self.stats.engine_pages += 1
            if result.cache_hit:
                self.stats.cache_hits += 1
                self.log(f"  cache p.{page_number} docling")
            else:
                self.log(f"  engine p.{page_number} docling")
            return result if result.has_content else None
        except Exception as exc:
            score.reasons.append(f"docling_error:{type(exc).__name__}")
            score.route = "source-image" if self.page_images != "never" else "rules"
            self.stats.engine_errors += 1
            self.log(f"  fallback p.{page_number}: Docling 실패 → 규칙 엔진")
            return None

    def wants_source_image(self, page_number: int, engine_result: EnginePage | None = None) -> bool:
        if self.page_images == "always":
            return True
        if self.page_images == "never":
            return False
        score = self.scores.get(page_number)
        if score is None:
            return False
        if score.route == "source-image":
            return True
        if score.confidence < self.confidence_threshold:
            return True
        if engine_result is not None and "low_text_recall" in engine_result.reasons:
            return True
        if engine_result is not None and engine_result.confidence < self.confidence_threshold:
            return True
        return False

    def manifest(self) -> dict:
        pages = []
        for page_number in sorted(self.scores):
            data = self.scores[page_number].to_dict()
            if page_number in self.source_images:
                data["source_image"] = self.source_images[page_number]
            pages.append(data)
        return {
            "profile": self.profile,
            "ocr": self.ocr,
            "source_lang": self.source_lang,
            "page_images": self.page_images,
            "confidence_threshold": self.confidence_threshold,
            "stats": self.stats.to_dict(),
            "pages": pages,
        }


def create_pipeline(
    doc,
    source: Path,
    pages: list[int],
    *,
    profile: str = "balanced",
    ocr: str = "auto",
    source_lang: str = "en",
    page_images: str = "auto",
    confidence_threshold: float = 0.62,
    cache: bool = True,
    max_engine_pages: int | None = 80,
    source_label: str = "원본 페이지 보기",
    log=None,
) -> PipelineContext:
    logger = log or (lambda _message: None)
    has_docling = profile in {"auto", "balanced"} and docling_available()
    scoring_profile = "balanced" if profile in {"auto", "balanced"} else "fast"
    scores = score_pages(
        doc,
        sorted(set(pages)),
        profile=scoring_profile,
        confidence_threshold=confidence_threshold,
        engine_available=has_docling,
    )
    if page_images == "never":
        for score in scores.values():
            if score.route == "source-image":
                score.route = "rules"
                score.reasons.append("source_image_disabled")
    if has_docling and max_engine_pages is not None:
        engine_pages = sorted(
            (score for score in scores.values() if score.route == "docling"),
            key=lambda score: score.confidence,
        )
        for score in engine_pages[max(0, max_engine_pages):]:
            score.route = "source-image" if page_images != "never" else "rules"
            score.reasons.append("engine_page_limit")
    page_cache = PageCache(source, enabled=cache) if has_docling else None
    engine = (
        DoclingEngine(
            ocr=ocr,
            source_lang=source_lang,
            cache=page_cache,
            log=logger,
        )
        if has_docling else None
    )
    if profile == "balanced" and not has_docling:
        logger("  Docling 미설치: 규칙 엔진과 저신뢰 원본 보기로 계속합니다.")
    planned = {
        "rules": sum(score.route == "rules" for score in scores.values()),
        "docling": sum(score.route == "docling" for score in scores.values()),
        "source": sum(score.route == "source-image" for score in scores.values()),
    }
    logger(
        f"  quality rules={planned['rules']} docling={planned['docling']} "
        f"source={planned['source']} threshold={confidence_threshold:.2f}"
    )
    return PipelineContext(
        source=source,
        profile=profile,
        ocr=ocr,
        source_lang=source_lang,
        page_images=page_images,
        confidence_threshold=confidence_threshold,
        scores=scores,
        engine=engine,
        source_label=source_label,
        log=logger,
    )

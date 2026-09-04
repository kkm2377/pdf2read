from __future__ import annotations

import re
from collections.abc import Iterable

from pdf2read.model import PageMetrics, PageScore, Route

SUSPICIOUS = re.compile(r"[\ufffd\u029c\u026a]|CHECK\s*[▶▷►>]|[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _image_ratio(page) -> tuple[int, float]:
    area = max(1.0, float(page.rect.width) * float(page.rect.height))
    image_area = 0.0
    images = page.get_image_info()
    for image in images:
        x0, y0, x1, y1 = image.get("bbox", (0, 0, 0, 0))
        image_area += max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return len(images), min(1.0, image_area / area)


def page_metrics(page, page_number: int) -> PageMetrics:
    text = page.get_text("text") or ""
    compact = re.sub(r"\s+", "", text)
    words = page.get_text("words") or []
    spans = 0
    rotated_lines = 0
    fonts: set[str] = set()
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            direction = line.get("dir", (1.0, 0.0))
            if abs(float(direction[1])) > 0.2:
                rotated_lines += 1
            for span in line.get("spans", []):
                if (span.get("text") or "").strip():
                    spans += 1
                    fonts.add(str(span.get("font") or ""))
    images, image_ratio = _image_ratio(page)
    drawings = len(page.get_drawings())
    page_area_k = max(1.0, float(page.rect.width) * float(page.rect.height) / 1000)
    return PageMetrics(
        page=page_number,
        chars=len(compact),
        words=len(words),
        spans=spans,
        fonts=len(fonts),
        images=images,
        image_ratio=image_ratio,
        drawings=drawings,
        rotated_lines=rotated_lines,
        suspicious_chars=len(SUSPICIOUS.findall(text)),
        text_density=len(compact) / page_area_k,
    )


def score_page(
    page,
    page_number: int,
    *,
    profile: str = "balanced",
    confidence_threshold: float = 0.62,
    engine_available: bool = False,
) -> PageScore:
    metrics = page_metrics(page, page_number)
    reasons: list[str] = []
    confidence = 1.0

    if metrics.chars < 20 and metrics.image_ratio >= 0.45:
        confidence = 0.08
        reasons.append("scanned")
    else:
        if metrics.chars < 40:
            confidence -= 0.36
            reasons.append("sparse_text")
        elif metrics.text_density < 0.18:
            confidence -= 0.15
            reasons.append("low_text_density")
        if metrics.image_ratio > 0.72:
            confidence -= 0.22
            reasons.append("image_heavy")
        elif metrics.image_ratio > 0.42:
            confidence -= 0.1
            reasons.append("mixed_image_text")
        if metrics.drawings > 350:
            confidence -= 0.18
            reasons.append("drawing_heavy")
        rotated_ratio = metrics.rotated_lines / max(1, metrics.spans)
        if metrics.rotated_lines >= 4 and rotated_ratio >= 0.35:
            confidence -= 0.42
            reasons.append("rotated_text")
        if metrics.fonts > 18:
            confidence -= 0.08
            reasons.append("many_fonts")
        if metrics.suspicious_chars:
            rate = metrics.suspicious_chars / max(1, metrics.chars)
            confidence -= min(0.3, 0.08 + rate * 2.5)
            reasons.append("suspicious_glyphs")

    confidence = max(0.0, min(1.0, confidence))
    route: Route = "rules"
    if profile == "balanced" and confidence < confidence_threshold and engine_available:
        route = "docling"
    elif confidence < confidence_threshold and not engine_available:
        route = "source-image" if metrics.chars < 20 else "rules"
    return PageScore(
        page=page_number,
        confidence=confidence,
        reasons=reasons,
        route=route,
        metrics=metrics,
    )


def score_pages(
    doc,
    pages: Iterable[int],
    *,
    profile: str = "balanced",
    confidence_threshold: float = 0.62,
    engine_available: bool = False,
) -> dict[int, PageScore]:
    return {
        pn: score_page(
            doc[pn - 1],
            pn,
            profile=profile,
            confidence_threshold=confidence_threshold,
            engine_available=engine_available,
        )
        for pn in pages
    }

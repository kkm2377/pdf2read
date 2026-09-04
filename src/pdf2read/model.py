from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockKind = Literal[
    "heading",
    "paragraph",
    "list_item",
    "table",
    "figure",
    "caption",
    "formula",
    "question",
    "choice",
    "note",
    "raw",
]
Route = Literal["rules", "docling", "source-image"]


@dataclass(frozen=True)
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


@dataclass
class Block:
    kind: BlockKind
    page: int
    text: str = ""
    html: str = ""
    bbox: BBox | None = None
    order: int = 0
    confidence: float = 1.0
    source: str = "rules"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PageMetrics:
    page: int
    chars: int
    words: int
    spans: int
    fonts: int
    images: int
    image_ratio: float
    drawings: int
    rotated_lines: int
    suspicious_chars: int
    text_density: float


@dataclass
class PageScore:
    page: int
    confidence: float
    reasons: list[str]
    route: Route
    metrics: PageMetrics
    engine_confidence: float | None = None

    @property
    def effective_confidence(self) -> float:
        return self.engine_confidence if self.engine_confidence is not None else self.confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "route": self.route,
            "engine_confidence": (
                round(self.engine_confidence, 3)
                if self.engine_confidence is not None else None
            ),
            "metrics": {
                "chars": self.metrics.chars,
                "words": self.metrics.words,
                "spans": self.metrics.spans,
                "fonts": self.metrics.fonts,
                "images": self.metrics.images,
                "image_ratio": round(self.metrics.image_ratio, 3),
                "drawings": self.metrics.drawings,
                "rotated_lines": self.metrics.rotated_lines,
                "suspicious_chars": self.metrics.suspicious_chars,
                "text_density": round(self.metrics.text_density, 3),
            },
        }


@dataclass
class EnginePage:
    page: int
    blocks: list[Block] = field(default_factory=list)
    main_html: str = ""
    notes_html: str = ""
    confidence: float = 0.0
    engine: str = "rules"
    reasons: list[str] = field(default_factory=list)
    source_image: str | None = None
    cache_hit: bool = False

    @property
    def has_content(self) -> bool:
        return bool(self.main_html.strip() or any(b.text.strip() or b.html.strip() for b in self.blocks))

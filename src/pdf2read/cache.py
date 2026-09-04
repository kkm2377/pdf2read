from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pdf2read.model import EnginePage

CACHE_SCHEMA = "4"


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PageCache:
    def __init__(self, source: Path, enabled: bool = True, root: Path | None = None):
        self.enabled = enabled
        self.source_hash = file_fingerprint(source) if enabled else ""
        default_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        self.root = (root or default_root / "pdf2read") / self.source_hash[:20]

    def _path(self, page: int, engine: str, version: str, options: dict) -> Path:
        raw = json.dumps(
            {
                "schema": CACHE_SCHEMA,
                "page": page,
                "engine": engine,
                "version": version,
                "options": options,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        key = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return self.root / f"{page:05d}-{key}.json"

    def load(self, page: int, engine: str, version: str, options: dict) -> EnginePage | None:
        if not self.enabled:
            return None
        path = self._path(page, engine, version, options)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return EnginePage(
                page=page,
                main_html=str(data.get("main_html") or ""),
                notes_html=str(data.get("notes_html") or ""),
                confidence=float(data.get("confidence") or 0),
                engine=engine,
                reasons=[str(x) for x in data.get("reasons") or []],
                cache_hit=True,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def store(self, result: EnginePage, version: str, options: dict) -> None:
        if not self.enabled or not result.has_content:
            return
        path = self._path(result.page, result.engine, version, options)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "main_html": result.main_html,
            "notes_html": result.notes_html,
            "confidence": result.confidence,
            "reasons": result.reasons,
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)

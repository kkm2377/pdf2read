from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pdf2read.model import EnginePage


class PageEngine(Protocol):
    name: str
    version: str

    def extract_page(self, source: Path, page_number: int) -> EnginePage:
        ...

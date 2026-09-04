from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


class HtmlAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.refs: list[str] = []
        self.images = 0
        self.images_with_alt = 0
        self.lang = ""
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"script", "style"}:
            self._ignored += 1
        if tag == "html":
            self.lang = values.get("lang", "")
        if tag == "img":
            self.images += 1
            if values.get("alt", "").strip():
                self.images_with_alt += 1
        for key in ("href", "src"):
            value = values.get(key, "")
            if value and not value.startswith(("#", "http:", "https:", "mailto:", "data:", "/")):
                self.refs.append(value.split("#", 1)[0].split("?", 1)[0])

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        if not self._ignored:
            self.text.append(data)


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def ngram_recall(expected: str, actual: str, size: int = 3) -> float:
    expected = normalize(expected)
    actual = normalize(actual)
    if len(expected) < size:
        return 1.0 if expected in actual else 0.0
    wanted = Counter(expected[i:i + size] for i in range(len(expected) - size + 1))
    got = Counter(actual[i:i + size] for i in range(len(actual) - size + 1))
    matched = sum(min(count, got[token]) for token, count in wanted.items())
    return matched / max(1, sum(wanted.values()))


def audit_output(out: Path) -> dict:
    missing: list[str] = []
    text: list[str] = []
    images = alt_images = 0
    languages: list[str] = []
    for html_file in sorted(out.glob("*.html")):
        audit = HtmlAudit()
        audit.feed(html_file.read_text(encoding="utf-8"))
        text.extend(audit.text)
        images += audit.images
        alt_images += audit.images_with_alt
        languages.append(audit.lang)
        for ref in audit.refs:
            if ref and not (html_file.parent / ref).exists():
                missing.append(f"{html_file.name}: {ref}")
    return {
        "text": " ".join(text),
        "missing_refs": missing,
        "images": images,
        "images_with_alt": alt_images,
        "languages": languages,
    }


def appears_in_order(text: str, phrases: list[str]) -> bool:
    cursor = 0
    for phrase in phrases:
        index = text.find(phrase, cursor)
        if index < 0:
            return False
        cursor = index + len(phrase)
    return True

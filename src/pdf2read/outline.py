from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Unit:
    id: str
    file: str
    title: str
    no: str
    level: int
    start: int
    end: int
    chapter_title: str
    sec_title: str
    kind: str
    children: list[str] = field(default_factory=list)

    @property
    def pages_label(self) -> str:
        if self.start == self.end:
            return str(self.start)
        return f"{self.start}–{self.end}"

    @property
    def pdf_pages(self) -> list[int]:
        return list(range(self.start, self.end + 1))


def _no_from_title(title: str, fallback: str) -> str:
    m = re.match(r"^(\d+(?:-\d+)+)(?:\s|$)", title)
    if m:
        return m.group(1)
    m = re.match(r"^第\s*(\d+)\s*章", title)
    if m:
        return m.group(1)
    return fallback


def _clean_title(title: str) -> str:
    t = title.strip()
    t = re.sub(r"^第\s*\d+\s*章\s*", "", t).strip()
    # Only strip textbook numbers like 1-1-2, not "2要素認証".
    t = re.sub(r"^(\d+(?:-\d+)+)\s+", "", t).strip()
    t = re.sub(r"[\x00-\x08]+", "", t)
    return t or title.strip()


def units_from_outline(toc: list, page_count: int, start: int | None, end: int | None) -> list[Unit]:
    entries = [(int(lv), str(title).strip(), int(pg)) for lv, title, pg in toc if int(pg) >= 1]
    if not entries:
        return []

    last_ch = ""
    last_sec = ""
    units: list[Unit] = []
    used_ids: set[str] = set()

    for i, (lv, title, pg) in enumerate(entries):
        if lv <= 1:
            last_ch = title
            last_sec = ""
        elif lv == 2:
            last_sec = title

        next_pg = entries[i + 1][2] if i + 1 < len(entries) else page_count + 1
        last_page = next_pg - 1
        if last_page < pg:
            continue

        if start and last_page < start:
            continue
        if end and pg > end:
            continue

        u_start = max(pg, start or pg)
        u_end = min(last_page, end or last_page)
        if u_end < u_start:
            continue

        fallback = f"u{len(units) + 1:03d}"
        uid = _no_from_title(title, fallback)
        base = uid
        n = 2
        while uid in used_ids:
            uid = f"{base}-{n}"
            n += 1
        used_ids.add(uid)

        next_lv = entries[i + 1][0] if i + 1 < len(entries) else lv
        kind = "unit"
        if lv <= 1 and next_lv > lv and (u_end - u_start) <= 1:
            kind = "opener"
        elif lv <= 1:
            kind = "front"

        units.append(
            Unit(
                id=uid,
                file=f"{uid}.html",
                title=_clean_title(title),
                no=uid,
                level=lv,
                start=u_start,
                end=u_end,
                chapter_title=last_ch,
                sec_title=last_sec if lv >= 2 else "",
                kind=kind,
            )
        )
    return units


def units_by_chunks(page_count: int, start: int, end: int, chunk: int) -> list[Unit]:
    units = []
    a = start
    i = 1
    while a <= end:
        b = min(end, a + chunk - 1)
        uid = f"p{a:03d}"
        units.append(
            Unit(
                id=uid,
                file=f"{uid}.html",
                title=f"p.{a}" if a == b else f"p.{a}–{b}",
                no=str(i),
                level=1,
                start=a,
                end=b,
                chapter_title="",
                sec_title="",
                kind="unit",
            )
        )
        a = b + 1
        i += 1
    return units


_SKIP_VISUAL = re.compile(r"^(?:目\s*次|索\s*引|もくじ|contents|index)$", re.I)
_QUESTION_TITLE = re.compile(r"^問\s*\d+")


def units_from_visual_titles(doc, start: int, end: int) -> list[Unit]:
    """When a PDF has no outline, split on large titles near the top of a page."""
    hits: list[tuple[int, str]] = []
    for pn in range(start, end + 1):
        page = doc[pn - 1]
        candidates: list[tuple[float, float, str]] = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans") or []
                if not spans:
                    continue
                text = "".join(s.get("text") or "" for s in spans).strip()
                size = max(float(s.get("size") or 0) for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                if not text or y0 > 170 or size < 15.0:
                    continue
                if re.fullmatch(r"\d{1,3}", text):
                    continue
                if _SKIP_VISUAL.match(text) or _QUESTION_TITLE.match(text):
                    continue
                if not (3 <= len(text) <= 48):
                    continue
                candidates.append((size, y0, text))
        if not candidates:
            continue
        max_size = max(c[0] for c in candidates)
        top = [c for c in candidates if c[0] >= max_size - 0.4]
        top.sort(key=lambda c: (c[1], -len(c[2])))
        hits.append((pn, top[0][2]))
    if len(hits) < 2:
        return []
    units: list[Unit] = []
    used: set[str] = set()
    for i, (pg, title) in enumerate(hits):
        next_pg = hits[i + 1][0] if i + 1 < len(hits) else end + 1
        last = min(end, next_pg - 1)
        if last < pg:
            continue
        uid = _no_from_title(title, f"p{pg:03d}")
        base = uid
        n = 2
        while uid in used:
            uid = f"{base}-{n}"
            n += 1
        used.add(uid)
        units.append(
            Unit(
                id=uid,
                file=f"{uid}.html",
                title=_clean_title(title),
                no=uid,
                level=1,
                start=pg,
                end=last,
                chapter_title=title,
                sec_title="",
                kind="unit",
            )
        )
    return units


def attach_chapter_maps(units: list[Unit]) -> None:
    by_ch: dict[str, list[Unit]] = {}
    for u in units:
        if u.kind == "opener":
            by_ch.setdefault(u.chapter_title, [])
        elif u.chapter_title:
            by_ch.setdefault(u.chapter_title, []).append(u)
    for u in units:
        if u.kind == "opener":
            kids = by_ch.get(u.chapter_title, [])
            u.children = [f"{k.no}　{k.title}" for k in kids if k is not u]

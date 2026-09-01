from __future__ import annotations

from collections import Counter


def detect_columns(doc, sample_pages: list[int]) -> dict:
    page = doc[sample_pages[0] - 1]
    width = float(page.rect.width)
    height = float(page.rect.height)
    xs: list[float] = []
    sizes: list[float] = []
    for pn in sample_pages:
        p = doc[pn - 1]
        for block in p.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    x0 = float(span["bbox"][0])
                    if 20 < x0 < width - 20:
                        xs.append(x0)
                    sizes.append(float(span.get("size") or 0))
    body = 9.0
    if sizes:
        sizes.sort()
        body = sizes[len(sizes) // 2]

    split = width * 0.68
    mode = "one"
    if xs:
        bins = Counter(int(x // 8) * 8 for x in xs)
        ordered = sorted(bins.items())
        if ordered:
            peaks = sorted(ordered, key=lambda kv: kv[1], reverse=True)[:4]
            peaks = sorted(peaks, key=lambda kv: kv[0])
            left = peaks[0][0]
            right_candidates = [p for p in peaks if p[0] > width * 0.58]
            if right_candidates and right_candidates[0][1] >= max(8, peaks[0][1] * 0.08):
                mode = "two"
                right_x = min(p[0] for p in right_candidates)
                split = max(width * 0.58, right_x - 10)
    return {"mode": mode, "split_x": split, "width": width, "height": height, "body_size": body}


def running_headers(doc, pages: list[int], layout: dict) -> set[str]:
    top_y = layout["height"] * 0.075
    bot_y = layout["height"] * 0.93
    counts: Counter[str] = Counter()
    sample = pages[: min(80, len(pages))]
    for pn in sample:
        page = doc[pn - 1]
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans") or []
                if not spans:
                    continue
                text = "".join(s.get("text") or "" for s in spans).strip()
                y0 = min(s["bbox"][1] for s in spans)
                if not text or len(text) > 40:
                    continue
                if y0 <= top_y or y0 >= bot_y:
                    counts[text] += 1
    need = max(3, int(len(sample) * 0.18))
    return {t for t, n in counts.items() if n >= need}

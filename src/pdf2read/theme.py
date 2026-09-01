from __future__ import annotations

from collections import Counter


def _rgb_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(r * 255))),
        max(0, min(255, int(g * 255))),
        max(0, min(255, int(b * 255))),
    )


def _sat(rgb: tuple[float, float, float]) -> float:
    return max(rgb) - min(rgb)


def extract_theme(doc, sample_pages: list[int]) -> dict:
    fills: Counter[tuple[float, float, float]] = Counter()
    inks: Counter[int] = Counter()
    for pn in sample_pages:
        page = doc[pn - 1]
        for d in page.get_drawings():
            fill = d.get("fill")
            if not fill or len(fill) < 3:
                continue
            rgb = (float(fill[0]), float(fill[1]), float(fill[2]))
            if _sat(rgb) < 0.18:
                continue
            if max(rgb) < 0.12:
                continue
            fills[tuple(round(c, 3) for c in rgb)] += 1
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    inks[int(span.get("color") or 0)] += len(span.get("text") or "")

    accent = (0.886, 0.424, 0.145)
    if fills:
        accent = fills.most_common(1)[0][0]
    ink = (0.173, 0.157, 0.141)
    if inks:
        c = inks.most_common(1)[0][0]
        ink = (((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255)

    accent_hex = _rgb_hex(*accent)
    deep = _rgb_hex(*(max(0, c * 0.82) for c in accent))
    soft = _rgb_hex(*tuple(min(1.0, c + (1 - c) * 0.82) for c in accent))
    line = _rgb_hex(*tuple(min(1.0, c + (1 - c) * 0.55) for c in accent))
    return {
        "accent": accent_hex,
        "accent_deep": deep,
        "accent_soft": soft,
        "accent_line": line,
        "ink": _rgb_hex(*ink),
        "paper": "#fffdfb",
        "page_bg": "#efe7dc",
    }


def theme_css(theme: dict) -> str:
    return f""":root {{
  --accent: {theme['accent']};
  --accent-deep: {theme['accent_deep']};
  --accent-ink: {theme['accent_deep']};
  --accent-soft: {theme['accent_soft']};
  --accent-line: {theme['accent_line']};
  --paper: {theme['paper']};
  --page-bg: {theme['page_bg']};
  --ink: {theme['ink']};
  --muted: #6d655e;
  --rule: #eadfd4;
  --sidebar: #faf6f1;
  --banner: {theme['accent']};
}}
"""

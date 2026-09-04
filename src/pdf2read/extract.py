from __future__ import annotations

import html
import re
from collections import Counter
from pathlib import Path

NOTE_LABELS = (
    "勉強のコツ", "用語", "参考", "関連", "発展", "過去問題をチェック",
    "補足", "ポイント", "注意", "MEMO", "Hint", "側注",
)
ITEM_START = re.compile(
    r"^(?:[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|●|•|・|◦|□|■|◆|(?:\d+[\.．])\s)"
)
HEAD_START = re.compile(
    r"^(?:問\d+|〔|①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|●|•|・|□|《解答》|"
    r"[ア-ンA-D][\s　\.．、]|[(（]\d+[)）]|\d+[\.．]\s)"
)
CHOICE = re.compile(r"^([ア-ンA-Da-d])[\s　\.．、](.*)$")
QHEAD = re.compile(r"^問\s*\d+")
SENTENCE_END = ("。", "？", "！", "．")
BOX_CHARS = "□■▢☐◻▪▫"
CHECK_WIDGET = re.compile(rf"CHECK\s*[▶▷►>]\s*[{BOX_CHARS}\s]*")
ONLY_BOXES = re.compile(rf"^[{BOX_CHARS}\s]+$")
# RyuminPro maps dotted leaders (……) to small-capital H.
LEADER_RUN = re.compile(r"[\t ]*[\u029c\u026a]+[\t ]*")


def clean_extracted_text(t: str) -> str:
    """Drop study-check widgets, lone boxes, and PDF leader-dot garbage."""
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b\ufeff]", "", t or "")
    t = CHECK_WIDGET.sub(" ", t)
    t = LEADER_RUN.sub(" …… ", t)
    t = t.replace("\t", " ")
    t = re.sub(rf"^[{BOX_CHARS}]+", "", t)
    t = re.sub(r" {2,}", " ", t).strip()
    if not t or ONLY_BOXES.match(t):
        return ""
    return t


def is_duplicate_title(t: str, extra: set[str] | None) -> bool:
    """True only when the line *is* a running title, not a sentence that starts with it."""
    return bool(extra and t and t in extra)


def line_inside_box(
    L: dict,
    box,
    pad: float = 2,
    *,
    preserve_body: bool = False,
    body_size: float = 9,
) -> bool:
    """Skip figure *labels*, not body lines that merely wrap around a diagram."""
    lw = L["x1"] - L["x0"]
    bw = box[2] - box[0]
    if bw > 0 and lw > bw * 0.82:
        return False
    cx = (L["x0"] + L["x1"]) / 2
    cy = (L["y0"] + L["y1"]) / 2
    inside = box[0] - pad <= cx <= box[2] + pad and box[1] - pad <= cy <= box[3] + pad
    if not inside:
        return False
    if preserve_body:
        text = clean_extracted_text(L["text"])
        if L["size"] >= body_size * 0.9 and len(text) >= 12:
            return False
    return True


def has_two_content_columns(lines: list[dict], layout: dict) -> bool:
    """Detect dense two-up content inside the main area (not the narrow notes column)."""
    split = layout["split_x"] if layout["mode"] == "two" else layout["width"]
    body = layout["body_size"]
    width = layout["width"]
    candidates = [
        L for L in lines
        if L["size"] >= body * 0.74
        and L["y0"] > 30
        and L["x0"] < split
        and len(clean_extracted_text(L["text"])) >= 3
    ]
    left = [L for L in candidates if L["x0"] < width * 0.4]
    right = [L for L in candidates if width * 0.45 <= L["x0"] < split]
    if len(left) < 10 or len(right) < 10:
        return False
    right_bins = Counter(int(L["x0"] // 16) * 16 for L in right)
    return bool(right_bins and right_bins.most_common(1)[0][1] >= 5)


def order_page_items(items: list[dict], layout: dict, two_up: bool) -> list[dict]:
    if not two_up:
        return sorted(items, key=lambda L: (L["y0"], L["x0"]))
    mid = layout["width"] * 0.45
    return sorted(items, key=lambda L: (0 if L["x0"] < mid else 1, L["y0"], L["x0"]))


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def overlaps(bb, other, pad=3) -> bool:
    x0, y0, x1, y1 = bb
    ox0, oy0, ox1, oy1 = other
    return not (x1 < ox0 - pad or x0 > ox1 + pad or y1 < oy0 - pad or y0 > oy1 + pad)


def _sat(fill) -> float:
    if not fill or len(fill) < 3:
        return 0
    rgb = fill[:3]
    return max(rgb) - min(rgb)


def lines_from_page(page, clip=None) -> list[dict]:
    out = []
    data = page.get_text("dict", clip=clip) if clip else page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans") or []
            if not spans:
                continue
            text = "".join(s.get("text") or "" for s in spans).replace("\u00ad", "")
            if not text.strip():
                continue
            sizes = [float(s.get("size") or 0) for s in spans]
            flags = [int(s.get("flags") or 0) for s in spans]
            color = int(spans[0].get("color") or 0)
            bbox = [
                min(s["bbox"][0] for s in spans),
                min(s["bbox"][1] for s in spans),
                max(s["bbox"][2] for s in spans),
                max(s["bbox"][3] for s in spans),
            ]
            out.append({
                "text": text,
                "size": max(sizes),
                "bold": any(f & 2**4 for f in flags) or max(sizes) >= 11.5,
                "color": color,
                "x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3],
            })
    out.sort(key=lambda L: (L["y0"], L["x0"]))
    return stitch_question_marks(stitch_checkbox_items(out))


def stitch_checkbox_items(lines: list[dict]) -> list[dict]:
    """Join a standalone □ marker with the text printed immediately to its right."""
    markers = [
        i for i, line in enumerate(lines)
        if re.fullmatch(r"[□▢☐◻]+", line["text"].strip())
    ]
    if not markers:
        return lines
    used: set[int] = set()
    merged: list[dict] = []
    for marker_i in markers:
        marker = lines[marker_i]
        best = None
        for i, line in enumerate(lines):
            if i == marker_i or i in used or i in markers:
                continue
            if abs(line["y0"] - marker["y0"]) > 2.5:
                continue
            gap = line["x0"] - marker["x1"]
            if gap < -1 or gap > 36:
                continue
            if best is None or gap < best[0]:
                best = (gap, i)
        if best is None:
            continue
        text_i = best[1]
        text_line = lines[text_i]
        item = dict(text_line)
        item["text"] = marker["text"].strip() + " " + text_line["text"].strip()
        item["x0"] = marker["x0"]
        item["y0"] = min(marker["y0"], text_line["y0"])
        item["y1"] = max(marker["y1"], text_line["y1"])
        used.update({marker_i, text_i})
        merged.append(item)
    out = [line for i, line in enumerate(lines) if i not in used]
    out.extend(merged)
    out.sort(key=lambda L: (L["y0"], L["x0"]))
    return out


def stitch_question_marks(lines: list[dict]) -> list[dict]:
    """Join a large '1' next to a small '問' into a heading 問1."""
    if not lines:
        return lines
    nums, marks = [], []
    for i, L in enumerate(lines):
        t = L["text"].strip()
        if re.fullmatch(r"\d{1,2}", t) and L["size"] >= 16:
            nums.append(i)
        elif t == "問":
            marks.append(i)
    if not nums or not marks:
        return lines
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for ni in nums:
        nL = lines[ni]
        best = None
        for mi in marks:
            if mi in used:
                continue
            mL = lines[mi]
            if abs(mL["y0"] - nL["y0"]) > 30:
                continue
            horizontal_gap = nL["x0"] - mL["x1"]
            if horizontal_gap < -4 or horizontal_gap > 60:
                continue
            dist = abs(mL["y0"] - nL["y0"]) + abs(mL["x0"] - nL["x0"])
            if best is None or dist < best[0]:
                best = (dist, mi)
        if best:
            used.add(ni)
            used.add(best[1])
            pairs.append((ni, best[1]))
    if not pairs:
        return lines
    drop = {i for pair in pairs for i in pair}
    extra = []
    for ni, _mi in pairs:
        nL = lines[ni]
        q = dict(nL)
        q["text"] = f"問{nL['text'].strip()}"
        q["bold"] = True
        q["y0"] = nL["y0"] - 0.2
        extra.append(q)
    out = [L for i, L in enumerate(lines) if i not in drop]
    out.extend(extra)
    out.sort(key=lambda L: (L["y0"], L["x0"]))
    return out


def skip_line(L: dict, layout: dict, headers: set[str], extra: set[str] | None = None) -> bool:
    t = clean_extracted_text(L["text"])
    if not t:
        return True
    if t in headers:
        return True
    if is_duplicate_title(t, extra):
        return True
    if t in {"頻出度"} or re.fullmatch(r"★+", t):
        return True
    if re.fullmatch(r"\d+(?:-\d+)+", t):
        return True
    if re.match(r"^\d-\d(?:-\d)?[\s　]", t):
        return True
    body = layout["body_size"]
    if L["size"] < body * 0.78 and len(t) <= 6:
        return True
    if re.fullmatch(r"\d{1,3}", t) and (L["y0"] < 42 or L["y0"] > layout["height"] * 0.91):
        return True
    if L["y0"] < 24 and L["size"] < body * 0.9:
        return True
    if L["size"] >= 18 and L["y0"] < 88 and not re.fullmatch(r"\d{1,2}", t) and not re.match(r"^問\s*\d+", t):
        return True
    if L["color"] == 16777215 and (L["size"] >= 16 or L["x0"] > layout["width"] * 0.78):
        return True
    return False


def find_tables(page) -> list[tuple]:
    found = []
    try:
        tabs = page.find_tables()
    except Exception:
        return found
    for t in tabs.tables:
        if t.bbox[3] - t.bbox[1] < 40:
            continue
        rows = t.extract()
        if not rows or len(rows) < 2:
            continue
        found.append((tuple(t.bbox), rows))
    return found


def table_html(rows: list) -> str:
    head = [clean_extracted_text(c or "") for c in rows[0]]
    if not any(head):
        return ""
    parts = ['<div class="table-wrap"><table class="book-table">']
    parts.append("<thead><tr>" + "".join(f"<th>{esc(c)}</th>" for c in head) + "</tr></thead><tbody>")
    for row in rows[1:]:
        cells = [clean_extracted_text(c or "") for c in row]
        parts.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells) + "</tr>")
    parts.append("</tbody></table></div>")
    return "\n".join(parts)


def _merge_boxes(boxes: list, pad: float) -> list:
    items = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out: list[list] = []
        for b in items:
            hit = None
            for o in out:
                if overlaps(b, o, pad=pad):
                    o[0], o[1] = min(o[0], b[0]), min(o[1], b[1])
                    o[2], o[3] = max(o[2], b[2]), max(o[3], b[3])
                    hit = o
                    changed = True
                    break
            if hit is None:
                out.append(list(b))
        items = out
    return items


def find_callouts(page, layout: dict) -> list[dict]:
    """Peach/orange sentence boxes from the textbook."""
    w = layout["width"]
    found = []
    for d in page.get_drawings():
        fill = d.get("fill")
        r = d["rect"]
        if _sat(fill) < 0.12 or r.width < w * 0.45 or r.height < 40:
            continue
        if r.x0 > w * 0.28:
            continue
        txt = page.get_text("text", clip=r)
        if len(txt.strip()) <= 40 or txt.count("。") < 1:
            continue
        found.append({
            "clip": (r.x0, r.y0, r.x1, r.y1),
            "y0": r.y0,
        })
    return found


def callout_html(page, box: dict) -> str:
    lines = [clean_extracted_text(L["text"]) for L in lines_from_page(page, clip=box["clip"])]
    lines = [t for t in lines if t]
    if not lines:
        return ""
    title = ""
    body = lines
    if lines[0].startswith(("〔", "【")):
        title, body = lines[0], lines[1:]
    para = ""
    paras = []
    for t in body:
        para += t
        if t.endswith(("。", "？", "！")):
            paras.append(para)
            para = ""
    if para:
        paras.append(para)
    bits = []
    if title:
        bits.append(f'<div class="kicker">{esc(title)}</div>')
    bits.extend(f"<p>{esc(p)}</p>" for p in paras)
    return f'<aside class="callout">{"".join(bits)}</aside>'


def find_figures(page, layout: dict) -> list[dict]:
    w, h = layout["width"], layout["height"]
    imgs = []
    for im in page.get_image_info():
        x0, y0, x1, y1 = im["bbox"]
        if x1 - x0 >= 16 and y1 - y0 >= 16:
            imgs.append([x0, y0, x1, y1])
    clusters = _merge_boxes(imgs, pad=18)

    extras = []
    for d in page.get_drawings():
        r = d["rect"]
        fill = d.get("fill")
        if r.width < 28 or r.height < 18 or r.x0 > w * 0.72 or r.y0 < 42:
            continue
        txt = page.get_text("text", clip=r)
        if txt.count("。") >= 1:
            continue
        if r.width >= w * 0.38 and r.width <= w * 0.86 and r.height >= 50 and _sat(fill) >= 0.12:
            extras.append([r.x0, r.y0, r.x1, r.y1])
            continue
        if r.width <= 140 and r.height <= 140:
            extras.append([r.x0, r.y0, r.x1, r.y1])

    for e in extras:
        attached = False
        for c in clusters:
            if overlaps(e, c, pad=18):
                c[0], c[1] = min(c[0], e[0]), min(c[1], e[1])
                c[2], c[3] = max(c[2], e[2]), max(c[3], e[3])
                attached = True
                break
        if not attached and e[2] - e[0] >= w * 0.38:
            clusters.append(list(e))

    figs = []
    for c in clusters:
        if c[2] - c[0] < 42 or c[3] - c[1] < 36:
            continue
        y0, y1 = c[1], c[3]
        cap = ""
        for L in lines_from_page(page):
            if L["size"] > 8.2:
                continue
            if L["x1"] - L["x0"] > w * 0.4:
                continue
            if L["y0"] < y0 - 18 or L["y0"] > y1 + 22:
                continue
            if L["x1"] < c[0] - 12 or L["x0"] > c[2] + 70:
                continue
            if L["y0"] >= y1 - 8 and 2 <= len(L["text"].strip()) <= 36:
                cap = L["text"].strip()
                c[3] = max(c[3], L["y1"])
        clip = (
            max(16, c[0] - 6),
            max(32, c[1] - 6),
            min(w - 8, c[2] + 8),
            min(h - 14, c[3] + 8),
        )
        figs.append({"clip": clip, "caption": cap or "図"})

    merged: list[dict] = []
    for fig in sorted(figs, key=lambda f: (f["clip"][1], f["clip"][0])):
        if any(overlaps(fig["clip"], m["clip"], pad=12) for m in merged):
            continue
        merged.append(fig)
    return merged


def clip_figures(page, figs: list[dict], dest: Path, prefix: str) -> None:
    import pymupdf
    dest.mkdir(parents=True, exist_ok=True)
    for i, fig in enumerate(figs, 1):
        name = f"{prefix}-{i}.png"
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.1, 2.1), clip=pymupdf.Rect(*fig["clip"]), alpha=False)
        pix.save(dest / name)
        fig["file"] = name
        if not fig.get("caption") or fig["caption"] == "図":
            txt = page.get_text("text", clip=fig["clip"])
            cap = re.sub(r"\s+", " ", txt).strip()
            fig["caption"] = cap[:28] if 2 <= len(cap) <= 28 else (fig.get("caption") or "図")


def is_heading(text: str, size: float, bold: bool, body: float) -> str | None:
    t = text.strip()
    if QHEAD.match(t):
        return "h3q"
    if re.fullmatch(r"\d+(?:-\d+)+", t):
        return None
    if t in {"解答と解説", "解答", "解説"}:
        return "h2ans"
    if t.startswith("《解答》"):
        return "anskey"
    if t.startswith("覚えよう"):
        return "remember"
    if size >= body * 1.55 and 2 <= len(t) <= 40:
        return "h2"
    if t.startswith(("•", "・", "◦")):
        return None
    if t.startswith("●") and 3 <= len(t) <= 28 and "。" not in t:
        return "h3"
    if bold and 2 <= len(t) <= 22 and size >= body * 0.95 and not t.endswith(("。", "．", "、", "です", "ます")):
        if not HEAD_START.match(t) and not ITEM_START.match(t):
            return "h3"
    if size >= body * 1.22 and 2 <= len(t) <= 28 and not t.endswith(("。", "．", "、", "です", "ます")):
        if not HEAD_START.match(t) and not ITEM_START.match(t):
            return "h3"
    return None


def structure_lines(lines: list[dict], body: float) -> list[tuple[str, object]]:
    acc: list[tuple[str, object]] = []
    buf = ""
    in_q = False
    in_ans = False
    in_remember = False
    remember: list[str] = []
    choices: list[tuple[str, str]] = []
    choice_line: dict | None = None
    remember_line: dict | None = None
    last_y: float | None = None

    def flush_p():
        nonlocal buf
        if buf:
            acc.append(("item", buf) if ITEM_START.match(buf) else ("p", buf))
            buf = ""

    def flush_q():
        nonlocal in_q, choices, choice_line
        if in_q and choices:
            acc.append(("choices", choices))
        choices = []
        in_q = False
        choice_line = None

    def flush_remember():
        nonlocal in_remember, remember, remember_line
        items = [x for x in remember if x]
        if items:
            acc.append(("remember", items))
        remember = []
        in_remember = False
        remember_line = None

    def push_heading(kind: str, text: str):
        if acc and acc[-1][0] in {"h2", "h3"}:
            prev = str(acc[-1][1])
            if prev.endswith(("と", "の", "を", "は", "が", "て", "で")):
                acc[-1] = (acc[-1][0], prev + text)
                return
        acc.append((kind, text))

    for i, L in enumerate(lines):
        if L.get("special"):
            flush_p()
            flush_q()
            flush_remember()
            acc.append(("raw", L["html"]))
            last_y = L.get("y0")
            continue
        raw = str(L.get("raw_text", L["text"])).strip()
        t = clean_extracted_text(L["text"])
        if not t:
            continue
        y = L.get("y0")
        gap = (y - last_y) if y is not None and last_y is not None else 0
        if y is not None:
            last_y = y
        kind = is_heading(t, L["size"], L["bold"], body)
        ch = CHOICE.match(t)
        if ch and ch.group(1).isascii() and re.match(r"^[〜～\-–—]\s*[A-Da-d]", ch.group(2)):
            ch = None

        if kind == "remember":
            flush_p()
            flush_q()
            in_remember = True
            continue
        if raw.startswith(("□", "▢", "☐", "◻")):
            flush_p()
            flush_q()
            in_remember = True
            remember.append(t)
            remember_line = L
            continue
        if in_remember and remember and remember_line:
            same_page = L.get("page") == remember_line.get("page")
            vertical_gap = L.get("y0", 0) - remember_line.get("y0", 0)
            indented = L.get("x0", 0) > remember_line.get("x0", 0) + body * 0.5
            if same_page and 0 <= vertical_gap <= body * 2 and indented:
                remember[-1] += t
                remember_line = L
                continue
        if in_remember:
            flush_remember()

        if kind == "h2ans":
            flush_p()
            flush_q()
            flush_remember()
            in_ans = True
            acc.append(("h2ans", t))
            continue
        if kind == "anskey":
            flush_p()
            acc.append(("anskey", t))
            continue
        if kind == "h3q":
            flush_p()
            flush_q()
            flush_remember()
            if in_ans:
                push_heading("h3", t)
                continue
            in_q = True
            acc.append(("h3q", t))
            continue
        if ch and (in_q or acc and acc[-1][0] in {"h3q", "choices"}):
            flush_p()
            if not in_q:
                in_q = True
            choices.append((ch.group(1), ch.group(2).strip()))
            choice_line = L
            continue
        if in_q and choices and not kind:
            last_m, last_t = choices[-1]
            same_page = choice_line is not None and L.get("page") == choice_line.get("page")
            vertical_gap = (
                L.get("y0", 0) - choice_line.get("y0", 0)
                if choice_line is not None else body * 99
            )
            indented = (
                choice_line is not None
                and L.get("x0", 0) >= choice_line.get("x0", 0) + body * 0.5
            )
            if (
                not last_t.endswith(SENTENCE_END)
                and same_page
                and 0 <= vertical_gap <= body * 2.5
                and indented
            ):
                choices[-1] = (last_m, last_t + t)
                choice_line = L
                continue
            flush_q()
        if kind in {"h2", "h3"}:
            flush_p()
            flush_q()
            flush_remember()
            push_heading(kind, t)
            continue
        if ITEM_START.match(t):
            flush_p()
            flush_remember()
            buf = t
            if t.endswith(SENTENCE_END):
                flush_p()
            continue
        if buf and ITEM_START.match(buf):
            ended = bool(re.search(r"(?:。|？|！|です|ます|である|など)$", buf))
            new_para = t.startswith(("その他", "また", "なお", "ただし", "例えば", "すなわち"))
            cont = t[:1] in "、。）」』てでをにがはもくとへより"
            if gap > 22 and not cont:
                flush_p()
            elif (ended and not cont) or new_para:
                flush_p()
            else:
                buf += t
                if t.endswith(SENTENCE_END):
                    flush_p()
                continue
        if buf and not buf.endswith(("。", "、", "：", ":", "；")):
            buf += t
        elif buf:
            buf += t
        else:
            buf = t
        if t.endswith(SENTENCE_END):
            if in_ans:
                acc.append(("ap", buf))
                buf = ""
            else:
                flush_p()
    flush_p()
    flush_q()
    flush_remember()
    return acc


def render_blocks(blocks: list[tuple[str, object]], unit_title: str) -> str:
    parts: list[str] = []
    q_open = False
    ans_open = False
    for kind, val in blocks:
        if kind in {"h2", "h3"} and val == unit_title:
            continue
        if kind == "h3q":
            if q_open:
                parts.append("</article>")
            parts.append(f"<article class='q-card'><h3>{esc(str(val))}</h3>")
            q_open = True
            continue
        if kind == "choices":
            items = "".join(
                f"<li><span class='mark'>{esc(m)}</span><span>{esc(t)}</span></li>" for m, t in val
            )
            chunk = f"<ul class='choices'>{items}</ul>"
            if q_open:
                parts.append(chunk + "</article>")
                q_open = False
            else:
                parts.append(chunk)
            continue
        if q_open and kind not in {"p"}:
            parts.append("</article>")
            q_open = False
        if kind == "h2ans":
            if not ans_open:
                parts.append("<details class='answer-block'><summary>解答と解説を見る</summary>")
                ans_open = True
            parts.append(f"<h2>{esc(str(val))}</h2>")
            continue
        if kind == "anskey":
            parts.append(f"<p class='ans'><span class='key'>{esc(str(val))}</span></p>")
            continue
        if kind == "h3":
            parts.append(f'<h3 class="sub">{esc(str(val))}</h3>')
        elif kind == "h2":
            parts.append(f"<h2>{esc(str(val))}</h2>")
        elif kind == "item":
            parts.append(f'<p class="item">{esc(str(val))}</p>')
        elif kind == "remember":
            items = "".join(f"<li>{esc(x)}</li>" for x in val)
            parts.append(f'<section class="remember"><h2>覚えよう</h2><ul>{items}</ul></section>')
        elif kind in {"p", "ap"}:
            parts.append(f"<p>{esc(str(val))}</p>")
        elif kind == "raw":
            parts.append(str(val))
    if q_open:
        parts.append("</article>")
    if ans_open:
        parts.append("</details>")
    return "\n".join(parts)


def group_notes(lines: list[dict]) -> str:
    if not lines:
        return ""
    groups: list[tuple[str, list[str]]] = []
    cur = "側注"
    buf: list[str] = []
    for L in lines:
        t = clean_extracted_text(L["text"])
        if not t:
            continue
        if t in NOTE_LABELS:
            if buf:
                groups.append((cur, buf))
            cur, buf = t, []
        else:
            buf.append(t)
    if buf:
        groups.append((cur, buf))
    html_parts = []
    for label, paras in groups:
        body = esc("".join(paras))
        if not body.strip():
            continue
        html_parts.append(
            f'<aside class="note"><header>{esc(label)}</header><p>{body}</p></aside>'
        )
    return "\n".join(html_parts)


def _source_page_item(doc, page_number: int, assets: Path, pipeline, layout: dict) -> dict | None:
    from pdf2read.pages import render_page_image

    try:
        if page_number in pipeline.source_images:
            src = pipeline.source_images[page_number]
        else:
            filename = render_page_image(doc[page_number - 1], assets / "pages", page_number)
            src = f"assets/pages/{filename}"
            pipeline.source_images[page_number] = src
            pipeline.stats.image_pages += 1
            pipeline.log(f"  source p.{page_number} ({filename.rsplit('.', 1)[-1]})")
        label = f"{pipeline.source_label} · p.{page_number}"
        score = pipeline.scores.get(page_number)
        open_by_default = bool(
            score
            and score.route == "source-image"
            and score.metrics.chars < 20
        )
        html_out = (
            f'<details class="source-page" data-source-page="{page_number}"'
            f'{" open" if open_by_default else ""}>'
            f"<summary>{esc(label)}</summary>"
            f'<div class="source-page-image"><img src="{esc(src)}" '
            f'alt="{esc(label)}" loading="lazy" decoding="async"></div></details>'
        )
        return {
            "text": "",
            "html": html_out,
            "special": "raw",
            "page": page_number,
            "y0": -1,
            "x0": 0,
            "x1": layout["width"],
            "y1": 0,
            "size": layout["body_size"],
            "bold": False,
            "color": 0,
        }
    except Exception as exc:
        pipeline.log(f"  source p.{page_number} 생성 실패: {type(exc).__name__}")
        return None


def extract_page_rules(
    page,
    page_number: int,
    layout: dict,
    headers: set[str],
    extra: set[str],
    assets: Path,
) -> tuple[list[dict], list[dict]]:
    extras = []
    tboxes = []
    for bbox, rows in find_tables(page):
        html_t = table_html(rows)
        if html_t:
            tboxes.append(bbox)
            extras.append({
                "text": "", "html": html_t, "special": "table",
                "y0": bbox[1], "x0": bbox[0], "page": page_number, "size": 10,
                "bold": False, "color": 0, "x1": bbox[2], "y1": bbox[3],
            })
    figs = find_figures(page, layout)
    clip_figures(page, figs, assets, f"fig-p{page_number:03d}")
    callouts = find_callouts(page, layout)
    figboxes = [f["clip"] for f in figs]
    callboxes = [c["clip"] for c in callouts]
    all_lines = lines_from_page(page)
    two_up = has_two_content_columns(all_lines, layout)
    main, side = [], []
    split = layout["split_x"] if layout["mode"] == "two" else layout["width"]
    for line in all_lines:
        line = dict(line)
        line["raw_text"] = line["text"]
        line["text"] = clean_extracted_text(line["text"])
        if skip_line(line, layout, headers, extra):
            continue
        if any(line_inside_box(line, box) for box in tboxes + callboxes):
            continue
        if any(
            line_inside_box(
                line,
                box,
                preserve_body=True,
                body_size=layout["body_size"],
            )
            for box in figboxes
        ):
            continue
        line["page"] = page_number
        if not two_up and layout["mode"] == "two" and line["x0"] >= split:
            side.append(line)
        else:
            main.append(line)
    for fig in figs:
        extras.append({
            "text": "", "special": "fig", "page": page_number, "y0": fig["clip"][1],
            "x0": fig["clip"][0], "x1": fig["clip"][2], "y1": fig["clip"][3],
            "size": 10, "bold": False, "color": 0,
            "html": (
                f'<figure class="diagram"><img src="assets/{fig["file"]}" alt="{esc(fig["caption"])}">'
                f"<figcaption>{esc(fig['caption'])}</figcaption></figure>"
            ),
        })
    for box in callouts:
        html_c = callout_html(page, box)
        if not html_c:
            continue
        extras.append({
            "text": "", "special": "callout", "page": page_number, "y0": box["y0"],
            "x0": box["clip"][0], "x1": box["clip"][2], "y1": box["clip"][3],
            "size": 10, "bold": False, "color": 0, "html": html_c,
        })
    return order_page_items(main + extras, layout, two_up), side


def extract_unit(
    doc,
    unit,
    layout: dict,
    headers: set[str],
    assets: Path,
    *,
    pipeline=None,
) -> tuple[str, str]:
    extra = {unit.no, unit.title, unit.sec_title, unit.chapter_title} - {""}
    notes_all = []
    kept_all = []
    for page_number in unit.pdf_pages:
        engine_result = pipeline.extract_with_engine(page_number) if pipeline else None
        source_item = None
        if pipeline and pipeline.wants_source_image(page_number, engine_result):
            source_item = _source_page_item(doc, page_number, assets, pipeline, layout)
            if source_item:
                kept_all.append(source_item)
        if engine_result and engine_result.has_content:
            kept_all.append({
                "text": "",
                "html": engine_result.main_html,
                "special": "raw",
                "page": page_number,
                "y0": 0,
                "x0": 0,
                "x1": layout["width"],
                "y1": layout["height"],
                "size": layout["body_size"],
                "bold": False,
                "color": 0,
            })
            continue
        score = pipeline.scores.get(page_number) if pipeline else None
        if (
            source_item is not None
            and score is not None
            and score.metrics.chars < 20
            and score.metrics.image_ratio >= 0.45
        ):
            continue
        main, side = extract_page_rules(
            doc[page_number - 1],
            page_number,
            layout,
            headers,
            extra,
            assets,
        )
        if pipeline and not main:
            score = pipeline.scores.get(page_number)
            if score:
                score.confidence = min(score.confidence, 0.1)
                score.route = "source-image"
                if "empty_rules_output" not in score.reasons:
                    score.reasons.append("empty_rules_output")
            if source_item is None and pipeline.wants_source_image(page_number):
                source_item = _source_page_item(doc, page_number, assets, pipeline, layout)
                if source_item:
                    kept_all.append(source_item)
        kept_all.extend(main)
        notes_all.extend(side)
        if pipeline:
            pipeline.stats.rules_pages += 1
    blocks = structure_lines(kept_all, layout["body_size"])
    return render_blocks(blocks, unit.title), group_notes(notes_all)

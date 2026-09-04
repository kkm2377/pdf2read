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
    if not extra or not t:
        return False
    if t in extra:
        return True
    if re.search(r"[。、．，!！?？]", t) or len(t) >= 28:
        return False
    for e in extra:
        if not e or len(e) < 4:
            continue
        if e.startswith(t) and 8 <= len(t) < len(e):
            return True
    return False


def line_inside_box(L: dict, box, pad: float = 2) -> bool:
    """Skip figure *labels*, not body lines that merely wrap around a diagram."""
    lw = L["x1"] - L["x0"]
    bw = box[2] - box[0]
    if bw > 0 and lw > bw * 0.82:
        return False
    cx = (L["x0"] + L["x1"]) / 2
    cy = (L["y0"] + L["y1"]) / 2
    return box[0] - pad <= cx <= box[2] + pad and box[1] - pad <= cy <= box[3] + pad


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
    return stitch_question_marks(out)


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
            if mL["x0"] > nL["x0"] + 12:
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
    if bold and 2 <= len(t) <= 22 and size >= body * 0.95 and not t.endswith(("。", "、", "です", "ます")):
        if not HEAD_START.match(t) and not ITEM_START.match(t):
            return "h3"
    if size >= body * 1.22 and 2 <= len(t) <= 28 and not t.endswith(("。", "、", "です", "ます")):
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
    last_y: float | None = None

    def flush_p():
        nonlocal buf
        if buf:
            acc.append(("item", buf) if ITEM_START.match(buf) else ("p", buf))
            buf = ""

    def flush_q():
        nonlocal in_q, choices
        if in_q:
            acc.append(("choices", choices))
            choices = []
            in_q = False

    def flush_remember():
        nonlocal in_remember, remember
        items = [x for x in remember if x]
        if items:
            acc.append(("remember", items))
        remember = []
        in_remember = False

    def push_heading(kind: str, text: str):
        if acc and acc[-1][0] in {"h2", "h3"}:
            prev = str(acc[-1][1])
            if prev.endswith(("と", "の", "を", "は", "が", "て", "で")) or (
                len(prev) <= 16 and len(text) <= 12 and "。" not in prev
            ):
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
        t = clean_extracted_text(L["text"])
        if not t:
            continue
        y = L.get("y0")
        gap = (y - last_y) if y is not None and last_y is not None else 0
        if y is not None:
            last_y = y
        kind = is_heading(t, L["size"], L["bold"], body)
        ch = CHOICE.match(t)

        if kind == "remember":
            flush_p()
            flush_q()
            in_remember = True
            continue
        if in_remember and t.startswith(("□", "■")):
            item = re.sub(rf"^[{BOX_CHARS}]+\s*", "", t).strip()
            if item:
                remember.append(item)
            continue

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
        if ch and (in_q or acc and acc[-1][0] in {"h3q", "choices", "p"}):
            flush_p()
            if not in_q:
                in_q = True
            choices.append((ch.group(1), ch.group(2).strip()))
            continue
        if in_q and choices and not kind:
            last_m, last_t = choices[-1]
            if not last_t.endswith(("。", "？", "！")):
                choices[-1] = (last_m, last_t + t)
                continue
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
            if t.endswith(("。", "？", "！")):
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
                if t.endswith(("。", "？", "！")):
                    flush_p()
                continue
        if buf and not buf.endswith(("。", "、", "：", ":", "；")):
            buf += t
        elif buf:
            buf += t
        else:
            buf = t
        if t.endswith(("。", "？", "！")):
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


def extract_unit(doc, unit, layout: dict, headers: set[str], assets: Path) -> tuple[str, str]:
    extra = {unit.no, unit.title, unit.sec_title, unit.chapter_title} - {""}
    notes_all = []
    kept_all = []
    split = layout["split_x"] if layout["mode"] == "two" else layout["width"]
    for pn in unit.pdf_pages:
        page = doc[pn - 1]
        extras = []
        tboxes = []
        for bbox, rows in find_tables(page):
            html_t = table_html(rows)
            if html_t:
                tboxes.append(bbox)
                extras.append({
                    "text": "", "html": html_t, "special": "table",
                    "y0": bbox[1], "x0": bbox[0], "page": pn, "size": 10, "bold": False,
                    "color": 0, "x1": bbox[2], "y1": bbox[3],
                })
        figs = find_figures(page, layout)
        clip_figures(page, figs, assets, f"fig-p{pn:03d}")
        callouts = find_callouts(page, layout)
        figboxes = [f["clip"] for f in figs]
        callboxes = [c["clip"] for c in callouts]
        skip_boxes = tboxes + figboxes + callboxes
        all_lines = lines_from_page(page)
        two_up = has_two_content_columns(all_lines, layout)
        main, side = [], []
        for L in all_lines:
            L = dict(L)
            L["text"] = clean_extracted_text(L["text"])
            if skip_line(L, layout, headers, extra):
                continue
            if any(line_inside_box(L, b) for b in skip_boxes):
                continue
            L["page"] = pn
            if not two_up and layout["mode"] == "two" and L["x0"] >= split:
                side.append(L)
            else:
                main.append(L)
        notes_all.extend(side)
        for fig in figs:
            extras.append({
                "text": "", "special": "fig", "page": pn, "y0": fig["clip"][1],
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
                "text": "", "special": "callout", "page": pn, "y0": box["y0"],
                "x0": box["clip"][0], "x1": box["clip"][2], "y1": box["clip"][3],
                "size": 10, "bold": False, "color": 0, "html": html_c,
            })
        kept_all.extend(order_page_items(main + extras, layout, two_up))
    blocks = structure_lines(kept_all, layout["body_size"])
    return render_blocks(blocks, unit.title), group_notes(notes_all)

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pdf2read.extract import esc
from pdf2read.outline import Unit, attach_chapter_maps
from pdf2read.theme import theme_css

VIEWER_DIR = Path(__file__).resolve().parent / "viewer"

UI = {
    "ko": {
        "hint": "Chrome에서 <strong>한국어로 번역</strong> · ← → 이동 · <strong>T</strong> 목차",
        "cover": "표지",
        "toc": "목차",
        "close": "닫기",
        "prev_lab": "이전",
        "next_lab": "다음",
        "small": "작게",
        "mid": "보통",
        "large": "크게",
        "resume": "이어서 읽기",
        "howto": "읽는 방법",
        "howto_1": "이 HTML을 로컬 서버로 연 뒤 Chrome 번역을 켭니다. 파일을 더블클릭하면 번역이 불안정합니다.",
        "howto_2": "목차 또는 T 키, 아래 이전/다음, 키보드 ← → 로 이동합니다.",
        "howto_3": "원본 PDF의 색·표·그림은 최대한 유지하고, 본문만 번역되도록 했습니다.",
        "map_hint": "← → 로 앞뒤 항목으로 이동합니다. T 키로 목차를 엽니다.",
        "answers": "解答と解説を見る",
        "library": "서재",
    },
    "en": {
        "hint": "Use Chrome <strong>Translate</strong> · ← → to move · <strong>T</strong> contents",
        "cover": "Cover",
        "toc": "Contents",
        "close": "Close",
        "prev_lab": "Previous",
        "next_lab": "Next",
        "small": "Small",
        "mid": "Medium",
        "large": "Large",
        "resume": "Resume",
        "howto": "How to read",
        "howto_1": "Open this folder via a local server, then translate the page in Chrome.",
        "howto_2": "Use Contents, T, or the arrow keys to move between sections.",
        "howto_3": "Colors, tables, and figures stay close to the PDF; only the text is meant to be translated.",
        "map_hint": "Use ← → to move. Press T for the table of contents.",
        "answers": "Show answers",
        "library": "Library",
    },
    "ja": {
        "hint": "Chromeの<strong>翻訳</strong>で読めます · ← → で移動 · <strong>T</strong> 目次",
        "cover": "表紙",
        "toc": "目次",
        "close": "閉じる",
        "prev_lab": "前へ",
        "next_lab": "次へ",
        "small": "小さく",
        "mid": "標準",
        "large": "大きく",
        "resume": "続きから",
        "howto": "読み方",
        "howto_1": "ローカルサーバで開き、Chrome翻訳をオンにします。",
        "howto_2": "目次、Tキー、← → で項目を移動します。",
        "howto_3": "色・表・図はPDFに近づけ、本文だけ翻訳される形にしています。",
        "map_hint": "← → で前後の項目へ。Tキーで目次。",
        "answers": "解答と解説を見る",
        "library": "書庫",
    },
}


def _shell(book_id: str, page_id: str, title: str, src_lang: str, ui: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="{esc(src_lang)}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="viewer/theme.css">
  <link rel="stylesheet" href="viewer/viewer.css">
</head>
<body class="ebook" data-page-id="{esc(page_id)}" data-book-id="{esc(book_id)}">
  <div class="chrome-bar" lang="{esc(ui.get('_lang','ko'))}" translate="no">
    <span>{ui['hint']}</span>
    <span class="spacer"></span>
    <nav class="chrome-actions">
      {f'<a class="nav-link" href="../">{esc(ui.get("library", "pdf2read"))}</a>' if ui.get("show_library") else ""}
      <a class="nav-link" href="index.html">{esc(ui['cover'])}</a>
      <button type="button" data-fs="s">{esc(ui['small'])}</button>
      <button type="button" data-fs="m">{esc(ui['mid'])}</button>
      <button type="button" data-fs="l">{esc(ui['large'])}</button>
    </nav>
  </div>
  <div class="ebook-rail" lang="{esc(ui.get('_lang','ko'))}" translate="no">
    <div class="ebook-top">
      <button class="toc-btn" id="toc-btn" type="button" aria-expanded="false">{esc(ui['toc'])}</button>
      <div class="ebook-where" id="ebook-where" lang="{esc(src_lang)}" translate="yes"></div>
      <span class="count" id="ebook-count"></span>
      <a class="nav-icon" id="nav-prev-top" aria-label="{esc(ui['prev_lab'])}">←</a>
      <a class="nav-icon" id="nav-next-top" aria-label="{esc(ui['next_lab'])}">→</a>
    </div>
    <div class="progress"><span id="ebook-progress"></span></div>
  </div>
  <div class="toc-overlay" id="toc-overlay"></div>
  <aside class="toc-drawer" id="toc-drawer" lang="{esc(src_lang)}">
    <header>
      <h2></h2>
      <button class="toc-btn" id="toc-close" type="button">{esc(ui['close'])}</button>
    </header>
    <nav class="toc-list" id="toc-list"></nav>
  </aside>
"""


FOOT = """
  <nav class="ebook-bottom">
    <a id="nav-prev-bottom"></a>
    <div class="pos" id="ebook-pos"></div>
    <a id="nav-next-bottom" class="next"></a>
  </nav>
  <script src="viewer/nav-data.js"></script>
  <script src="viewer/viewer.js"></script>
</body>
</html>
"""


def _opener_main(unit: Unit, units: list[Unit], ui: dict) -> str:
    kids = [u for u in units if u.chapter_title == unit.chapter_title and u.kind != "opener"]
    links = []
    for k in kids:
        links.append(
            f'<a href="{k.file}"><div class="no">{esc(k.no)}　p.{esc(k.pages_label)}</div>'
            f"<strong>{esc(k.title)}</strong></a>"
        )
    return (
        f'<nav class="chapter-map">{"".join(links)}</nav>'
        f'<p class="kbd-hint">{esc(ui["map_hint"])}</p>'
    )


def render_unit_html(book: dict, unit: Unit, units: list[Unit], main: str, notes: str, ui: dict, src_lang: str) -> str:
    if unit.kind == "opener":
        main = _opener_main(unit, units, ui)
        notes = ""
    kicker = ""
    if unit.kind != "opener":
        kicker = f'''
            <div class="section-kicker">
              <h2><span class="num">{esc(unit.no)}</span><span class="dot"></span>{esc(unit.title)}</h2>
            </div>
        '''
    banner_no = unit.no.split("-")[0] if unit.kind == "opener" else (unit.sec_title.split()[0] if unit.sec_title else unit.no)
    banner_title = unit.chapter_title or book["title"]
    if unit.sec_title:
        banner_title = unit.sec_title
    inner = f'''
  <div class="wrap">
    <article class="book">
      <div class="book-inner">
        <div class="running-head">
          <span>{esc(unit.chapter_title or book["title"])}</span>
          <span><span class="page-no">{esc(unit.pages_label)}</span></span>
        </div>
        <header class="chapter-banner">
          <span class="chapter-no">{esc(banner_no[:6])}</span>
          <h1>{esc(banner_title)}</h1>
        </header>
        <div class="spread">
          <div class="main">
            {kicker}
            {main}
          </div>
          <aside class="notes">{notes}</aside>
        </div>
      </div>
    </article>
  </div>
'''
    head = _shell(book["id"], unit.id, f'{unit.no} {unit.title} — {book["title"]}', src_lang, ui)
    return head + inner + FOOT


def render_index(book: dict, units: list[Unit], ui: dict, src_lang: str) -> str:
    chapters = []
    seen = set()
    for u in units:
        if u.kind == "opener" and u.chapter_title not in seen:
            seen.add(u.chapter_title)
            chapters.append(u)
    if not chapters:
        chapters = units
    compact = len(chapters) > 16
    cards = []
    for u in chapters:
        cards.append(
            f'<a class="card" href="{u.file}"><div class="kicker">p.{esc(u.pages_label)}</div>'
            f"<h2>{esc(u.chapter_title or u.title)}</h2></a>"
        )
    lang = ui.get("_lang", "ko")
    lib = (
        f'<a class="nav-link" href="../">{esc(ui.get("library", "pdf2read"))}</a>'
        if ui.get("show_library")
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="{esc(lang)}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(book["title"])}</title>
  <link rel="stylesheet" href="viewer/theme.css">
  <link rel="stylesheet" href="viewer/viewer.css">
</head>
<body data-book-id="{esc(book["id"])}">
  <div class="chrome-bar" lang="{esc(lang)}" translate="no">
    <span>{ui["hint"]}</span>
    <span class="spacer"></span>
    <nav class="chrome-actions">{lib}</nav>
  </div>
  <div class="wrap">
    <div class="book">
      <header class="home-hero">
        <span class="brand">pdf2read</span>
        <h1>{esc(book["title"])}</h1>
        <p id="resume-slot"></p>
      </header>
      <div class="cards{' compact' if compact else ''}">{"".join(cards)}</div>
      <section class="howto" translate="no">
        <h2>{esc(ui["howto"])}</h2>
        <ol>
          <li>{esc(ui["howto_1"])}</li>
          <li>{esc(ui["howto_2"])}</li>
          <li>{esc(ui["howto_3"])}</li>
        </ol>
      </section>
    </div>
  </div>
  <script src="viewer/nav-data.js"></script>
  <script>
    try {{
      const book = (window.BOOK_NAV || {{}}).bookId;
      const last = JSON.parse(localStorage.getItem("pdf2read-" + book) || "null");
      const slot = document.getElementById("resume-slot");
      if (last && slot) {{
        slot.innerHTML = '<a class="nav-link" href="' + last.file + '">{esc(ui["resume"])}: ' + last.no + "　" + last.title + "</a>";
      }}
    }} catch (e) {{}}
  </script>
</body>
</html>
"""


def write_book(
    out: Path,
    book: dict,
    units: list[Unit],
    doc,
    layout,
    headers,
    theme,
    ui: dict,
    src_lang: str,
    progress=None,
) -> None:
    from pdf2read.extract import extract_unit as ex

    log = progress or (lambda _m: None)
    attach_chapter_maps(units)
    viewer_out = out / "viewer"
    assets = out / "assets"
    viewer_out.mkdir(parents=True, exist_ok=True)
    assets.mkdir(exist_ok=True)
    shutil.copyfile(VIEWER_DIR / "viewer.css", viewer_out / "viewer.css")
    shutil.copyfile(VIEWER_DIR / "viewer.js", viewer_out / "viewer.js")
    (viewer_out / "theme.css").write_text(theme_css(theme), encoding="utf-8")

    nav = {
        "bookId": book["id"],
        "title": book["title"],
        "ui": {k: ui[k] for k in ("prev_lab", "next_lab", "toc") if k in ui},
        "pages": [
            {
                "id": u.id,
                "file": u.file,
                "no": u.no,
                "title": u.title,
                "pages": u.pages_label,
                "chapter_title": u.chapter_title,
                "sec_title": u.sec_title,
                "kind": u.kind,
            }
            for u in units
        ],
    }
    (viewer_out / "nav-data.js").write_text(
        "window.BOOK_NAV = " + json.dumps(nav, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    (out / "index.html").write_text(render_index(book, units, ui, src_lang), encoding="utf-8")

    for i, unit in enumerate(units, 1):
        main, notes = ex(doc, unit, layout, headers, assets)
        html_out = render_unit_html(book, unit, units, main, notes, ui, src_lang)
        (out / unit.file).write_text(html_out, encoding="utf-8")
        log(f"  [{i}/{len(units)}] {unit.file}")

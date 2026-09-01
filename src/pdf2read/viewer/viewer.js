(function polishChrome() {
  const bar = document.querySelector(".chrome-bar");
  if (!bar) return;
  document.querySelectorAll(".howto").forEach((el) => el.remove());
  const lang = bar.getAttribute("lang") || document.documentElement.lang || "ko";
  const L = {
    ko: { home: "pdf2read", titleTo: "타이틀로", hint: "← → 이동 · T 목차", small: "작게", mid: "보통", large: "크게" },
    en: { home: "pdf2read", titleTo: "Title", hint: "← → to move · T contents", small: "Small", mid: "Medium", large: "Large" },
    ja: { home: "pdf2read", titleTo: "タイトルへ", hint: "← → で移動 · T 目次", small: "小さく", mid: "標準", large: "大きく" },
  };
    const t = L[lang] || L.ko;
  const reading = document.body.classList.contains("ebook");
  bar.innerHTML =
    `<a class="nav-home" href="/">${t.home}</a>` +
    (reading ? `<span class="chrome-hint">${t.hint}</span>` : "") +
    `<span class="spacer"></span>` +
    `<nav class="chrome-actions">` +
    (reading ? `<a class="nav-link nav-title" href="index.html">${t.titleTo}</a>` : "") +
    `<button type="button" data-fs="s">${t.small}</button>` +
    `<button type="button" data-fs="m">${t.mid}</button>` +
    `<button type="button" data-fs="l">${t.large}</button>` +
    `</nav>`;
  const savedFs = localStorage.getItem("pdf2read-fs") || "m";
  document.documentElement.classList.add("fs-" + savedFs);
  bar.querySelectorAll("[data-fs]").forEach((btn) => {
    const size = btn.getAttribute("data-fs");
    btn.setAttribute("aria-pressed", size === savedFs ? "true" : "false");
    btn.addEventListener("click", () => {
      document.documentElement.classList.remove("fs-s", "fs-m", "fs-l");
      document.documentElement.classList.add("fs-" + size);
      localStorage.setItem("pdf2read-fs", size);
      bar.querySelectorAll("[data-fs]").forEach((b) => {
        b.setAttribute("aria-pressed", b.getAttribute("data-fs") === size ? "true" : "false");
      });
    });
  });
})();

(function () {
  const nav = window.BOOK_NAV;
  if (!nav || !document.body.classList.contains("ebook")) return;

  const pages = nav.pages;
  const id = document.body.dataset.pageId;
  const bookId = document.body.dataset.bookId || nav.bookId;
  const idx = pages.findIndex((p) => p.id === id);
  if (idx < 0) return;

  const cur = pages[idx];
  const prev = pages[idx - 1];
  const next = pages[idx + 1];
  const ui = nav.ui || {};

  const saved = localStorage.getItem("pdf2read-fs") || "m";
  document.documentElement.classList.add("fs-" + saved);

  function $(sel) { return document.querySelector(sel); }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  document.querySelectorAll("[data-fs]").forEach((btn) => {
    const size = btn.getAttribute("data-fs");
    btn.setAttribute("aria-pressed", size === saved ? "true" : "false");
    btn.addEventListener("click", () => {
      document.documentElement.classList.remove("fs-s", "fs-m", "fs-l");
      document.documentElement.classList.add("fs-" + size);
      localStorage.setItem("pdf2read-fs", size);
      document.querySelectorAll("[data-fs]").forEach((b) => {
        b.setAttribute("aria-pressed", b.getAttribute("data-fs") === size ? "true" : "false");
      });
    });
  });

  const where = $("#ebook-where");
  if (where) {
    where.innerHTML =
      `<span class="crumb">${escapeHtml(cur.chapter_title || nav.title || "")}</span>` +
      `<span class="here">${escapeHtml(cur.no + "　" + cur.title)}</span>`;
  }
  const count = $("#ebook-count");
  if (count) count.textContent = `${idx + 1} / ${pages.length}`;
  const bar = $("#ebook-progress");
  if (bar) bar.style.width = `${((idx + 1) / pages.length) * 100}%`;
  const pos = $("#ebook-pos");
  if (pos) pos.textContent = `${idx + 1} / ${pages.length}`;

  function fillLink(el, page) {
    if (!el) return;
    if (!page) {
      el.style.visibility = "hidden";
      el.removeAttribute("href");
      return;
    }
    el.href = page.file;
    el.title = page.no + "　" + page.title;
  }
  function fillBottom(el, page, label, isNext) {
    if (!el) return;
    if (!page) {
      el.style.visibility = "hidden";
      el.removeAttribute("href");
      return;
    }
    el.href = page.file;
    el.classList.toggle("next", !!isNext);
    el.innerHTML = `<span class="lab">${escapeHtml(label)}</span><span class="ttl">${escapeHtml(page.no + "　" + page.title)}</span>`;
  }
  fillLink($("#nav-prev-top"), prev);
  fillLink($("#nav-next-top"), next);
  fillBottom($("#nav-prev-bottom"), prev, ui.prev_lab || "Prev");
  fillBottom($("#nav-next-bottom"), next, ui.next_lab || "Next", true);

  const list = $("#toc-list");
  if (list) {
    let html = "";
    let lastCh = "";
    let lastSec = "";
    pages.forEach((p) => {
      if (p.chapter_title && p.chapter_title !== lastCh) {
        html += `<div class="sec chap">${escapeHtml(p.chapter_title)}</div>`;
        lastCh = p.chapter_title;
        lastSec = "";
      }
      if (p.sec_title && p.sec_title !== lastSec && p.kind !== "opener") {
        html += `<div class="sec">${escapeHtml(p.sec_title)}</div>`;
        lastSec = p.sec_title;
      }
      const cls = p.id === id ? "current" : "";
      html += `<a class="${cls}" href="${p.file}">${escapeHtml(p.no + "　" + p.title)}<span class="pg">p.${p.pages}</span></a>`;
    });
    list.innerHTML = html;
  }
  const tocTitle = document.querySelector(".toc-drawer h2");
  if (tocTitle) tocTitle.textContent = nav.title || "";

  const overlay = $("#toc-overlay");
  const drawer = $("#toc-drawer");
  function openToc(open) {
    overlay.classList.toggle("open", open);
    drawer.classList.toggle("open", open);
    document.getElementById("toc-btn")?.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) drawer.querySelector("a.current")?.focus();
  }
  document.getElementById("toc-btn")?.addEventListener("click", () => openToc(true));
  document.getElementById("toc-close")?.addEventListener("click", () => openToc(false));
  overlay?.addEventListener("click", () => openToc(false));

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea")) return;
    if (e.key === "Escape") openToc(false);
    if (e.key === "ArrowLeft" && prev) location.href = prev.file;
    if (e.key === "ArrowRight" && next) location.href = next.file;
    if (e.key === "t" || e.key === "T") openToc(!drawer.classList.contains("open"));
  });

  localStorage.setItem("pdf2read-" + bookId, JSON.stringify({
    id: cur.id, file: cur.file, title: cur.title, no: cur.no
  }));
  window.addEventListener("scroll", () => {
    localStorage.setItem("pdf2read-scroll-" + bookId + "-" + cur.id, String(window.scrollY));
  }, { passive: true });
  const y = Number(localStorage.getItem("pdf2read-scroll-" + bookId + "-" + cur.id) || 0);
  if (y > 80 && location.hash === "") {
    requestAnimationFrame(() => window.scrollTo(0, y));
  }
})();

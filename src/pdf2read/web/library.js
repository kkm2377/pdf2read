(function () {
  const COPY = {
    ko: {
      lang: "한국어",
      kicker: "PDF → HTML",
      headline: "PDF를 HTML로.",
      lead: "파일을 올리면 이 컴퓨터에서 바꿉니다. 번역은 Chrome이 합니다.",
      drop: "PDF를 놓거나 선택",
      hint: "로컬 변환 · 서버로 보내지 않습니다",
      convert: "변환",
      shelf: "서재",
      empty: "아직 책이 없습니다.",
      items: "항목",
      converting: "변환 중…",
      done: "완료",
      fail: "변환하지 못했습니다.",
      pick: "PDF를 먼저 선택하세요.",
    },
    en: {
      lang: "English",
      kicker: "PDF → HTML",
      headline: "PDF to HTML.",
      lead: "Files stay on this computer. Chrome does the translation.",
      drop: "Drop or choose a PDF",
      hint: "Local convert · nothing is uploaded",
      convert: "Convert",
      shelf: "Library",
      empty: "No books yet.",
      items: "sections",
      converting: "Converting…",
      done: "Done",
      fail: "Conversion failed.",
      pick: "Choose a PDF first.",
    },
    ja: {
      lang: "日本語",
      kicker: "PDF → HTML",
      headline: "PDFをHTMLに。",
      lead: "このコンピュータの中で変換します。翻訳はChromeが行います。",
      drop: "PDFを置くか選ぶ",
      hint: "ローカル変換 · 送信しません",
      convert: "変換",
      shelf: "書庫",
      empty: "まだ本がありません。",
      items: "項目",
      converting: "変換中…",
      done: "完了",
      fail: "変換できませんでした。",
      pick: "先にPDFを選んでください。",
    },
  };

  const sun = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="4"/><path stroke-linecap="round" d="M12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3 12h2M19 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const moon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 13a7 7 0 1 1-7-9 7 7 0 0 0 7 9Z"/></svg>';

  const file = document.getElementById("file");
  const drop = document.getElementById("dropzone");
  const form = document.getElementById("form");
  const nameEl = document.getElementById("filename");
  const logEl = document.getElementById("log");
  const go = document.getElementById("go");
  const booksEl = document.getElementById("books");
  const countEl = document.getElementById("count");
  const statusEl = document.getElementById("status");
  const progress = document.getElementById("progress");
  const langBtn = document.getElementById("lang-btn");
  const langMenu = document.getElementById("lang-menu");
  const themeBtn = document.getElementById("theme-btn");
  let chosen = null;

  function uiLang() {
    const v = localStorage.getItem("pdf2read-ui") || "ko";
    return COPY[v] ? v : "ko";
  }
  function t() { return COPY[uiLang()]; }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("pdf2read-theme", theme);
    themeBtn.innerHTML = theme === "dark" ? sun : moon;
    themeBtn.setAttribute("aria-label", theme === "dark" ? "Light" : "Dark");
  }
  function applyCopy() {
    const c = t();
    document.documentElement.lang = uiLang();
    langBtn.textContent = c.lang;
    document.getElementById("kicker").textContent = c.kicker;
    document.getElementById("headline").textContent = c.headline;
    document.getElementById("lead").textContent = c.lead;
    document.getElementById("drop-title").textContent = c.drop;
    document.getElementById("drop-hint").textContent = c.hint;
    go.textContent = c.convert;
    document.getElementById("shelf-title").textContent = c.shelf;
    langMenu.querySelectorAll("button").forEach((b) => {
      b.setAttribute("aria-selected", b.dataset.ui === uiLang() ? "true" : "false");
    });
    loadBooks();
  }

  const savedTheme = localStorage.getItem("pdf2read-theme")
    || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(savedTheme);
  applyCopy();

  themeBtn.addEventListener("click", () => {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
  langBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = langMenu.hidden;
    langMenu.hidden = !open;
    langBtn.setAttribute("aria-expanded", open ? "true" : "false");
  });
  langMenu.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-ui]");
    if (!btn) return;
    localStorage.setItem("pdf2read-ui", btn.dataset.ui);
    langMenu.hidden = true;
    langBtn.setAttribute("aria-expanded", "false");
    applyCopy();
  });
  document.addEventListener("click", () => {
    langMenu.hidden = true;
    langBtn.setAttribute("aria-expanded", "false");
  });

  function setFile(f) {
    if (!f) return;
    chosen = f;
    nameEl.textContent = f.name;
    statusEl.textContent = Math.max(1, Math.round(f.size / 1024)) + " KB";
  }

  drop.addEventListener("click", () => file.click());
  file.addEventListener("change", () => setFile(file.files[0]));
  ["dragenter", "dragover"].forEach((ev) => {
    form.addEventListener(ev, (e) => {
      e.preventDefault();
      form.classList.add("over");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    form.addEventListener(ev, (e) => {
      e.preventDefault();
      form.classList.remove("over");
    });
  });
  form.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  async function loadBooks() {
    const c = t();
    try {
      const res = await fetch("/api/books");
      const data = await res.json();
      const books = data.books || [];
      countEl.textContent = books.length ? String(books.length) : "";
      if (!books.length) {
        booksEl.innerHTML = `<p class="empty">${escapeHtml(c.empty)}</p>`;
        return;
      }
      booksEl.innerHTML = books.map((b) => (
        `<a class="book-card" href="${b.href}">` +
        `<small>${escapeHtml(b.id)} · ${b.units} ${escapeHtml(c.items)}</small>` +
        `<h3>${escapeHtml(b.title)}</h3>` +
        `</a>`
      )).join("");
    } catch (e) {
      booksEl.innerHTML = `<p class="empty">${escapeHtml(c.fail)}</p>`;
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const c = t();
    if (!chosen) {
      statusEl.textContent = c.pick;
      file.click();
      return;
    }
    const body = new FormData();
    body.append("pdf", chosen, chosen.name);
    body.append("lang", "auto");
    body.append("ui_lang", uiLang());
    go.disabled = true;
    progress.hidden = false;
    logEl.hidden = true;
    statusEl.textContent = c.converting;
    const res = await fetch("/api/convert", { method: "POST", body });
    const job = await res.json();
    if (!res.ok) {
      statusEl.textContent = job.error || c.fail;
      go.disabled = false;
      progress.hidden = true;
      return;
    }
    while (true) {
      await new Promise((r) => setTimeout(r, 600));
      const st = await fetch("/api/jobs/" + job.id).then((r) => r.json());
      if ((st.log || []).length) {
        logEl.hidden = false;
        logEl.textContent = st.log.join("\n");
        logEl.scrollTop = logEl.scrollHeight;
      }
      if (st.status === "done") {
        statusEl.textContent = c.done;
        progress.hidden = true;
        location.href = st.href;
        return;
      }
      if (st.status === "error") {
        statusEl.textContent = st.error || c.fail;
        go.disabled = false;
        progress.hidden = true;
        return;
      }
    }
  });
})();

(function () {
  const COPY = {
    ko: {
      lang: "한국어",
      kicker: "PDF → HTML",
      headline: "PDF를 HTML로.",
      lead: "이 컴퓨터에서 PDF를 HTML로 바꿉니다.",
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
      folder: "폴더",
      none: "책",
      newFolder: "새 폴더",
      folderName: "폴더 이름",
      dropHere: "책을 여기로 끌어다 놓으세요",
      del: "삭제",
      delFolder: "폴더 삭제",
      confirmDel: "이 HTML을 이 컴퓨터에서 지울까요?",
      confirmFolder: "폴더와 안의 책을 모두 지울까요?",
    },
    en: {
      lang: "English",
      kicker: "PDF → HTML",
      headline: "PDF to HTML.",
      lead: "Convert a PDF to HTML on this computer.",
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
      folder: "Folder",
      none: "Books",
      newFolder: "New folder",
      folderName: "Folder name",
      dropHere: "Drop a book here",
      del: "Delete",
      delFolder: "Delete folder",
      confirmDel: "Delete this HTML from this computer?",
      confirmFolder: "Delete this folder and the books inside?",
    },
    ja: {
      lang: "日本語",
      kicker: "PDF → HTML",
      headline: "PDFをHTMLに。",
      lead: "このコンピュータでPDFをHTMLにします。",
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
      folder: "フォルダ",
      none: "本",
      newFolder: "新しいフォルダ",
      folderName: "フォルダ名",
      dropHere: "本をここにドロップ",
      del: "削除",
      delFolder: "フォルダを削除",
      confirmDel: "このHTMLをこのコンピュータから消しますか？",
      confirmFolder: "フォルダと中の本を消しますか？",
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
  const newFolderBtn = document.getElementById("new-folder");
  let chosen = null;
  let folders = [];

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
    newFolderBtn.textContent = c.newFolder;
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
      folders = data.folders || [];
      countEl.textContent = books.length ? String(books.length) : "";
      if (!books.length && !folders.length) {
        booksEl.innerHTML = `<p class="empty">${escapeHtml(c.empty)}</p>`;
        return;
      }
      const groups = new Map();
      groups.set("", []);
      folders.forEach((f) => groups.set(f.id, []));
      books.forEach((b) => {
        const key = groups.has(b.folder) ? b.folder : "";
        groups.get(key).push(b);
      });
      const blocks = [];
      folders.forEach((f) => {
        const list = groups.get(f.id) || [];
        blocks.push(
          `<section class="folder-bin" data-drop-folder="${escapeHtml(f.id)}">` +
          `<header class="folder-tab">` +
          `<span class="folder-icon" aria-hidden="true"></span>` +
          `<h3>${escapeHtml(f.name)}</h3>` +
          `<button type="button" class="icon-del" data-del-folder="${escapeHtml(f.id)}" aria-label="${escapeHtml(c.delFolder)}">×</button>` +
          `</header>` +
          `<div class="folder-tray">` +
          (list.length ? list.map((b) => cardHtml(b, c)).join("") : `<p class="drop-hint">${escapeHtml(c.dropHere)}</p>`) +
          `</div></section>`
        );
      });
      const loose = groups.get("") || [];
      if (loose.length || !folders.length) {
        blocks.push(
          `<section class="loose" data-drop-folder="">` +
          `<header><h3>${escapeHtml(c.none)}</h3></header>` +
          `<div class="books">` +
          (loose.length ? loose.map((b) => cardHtml(b, c)).join("") : `<p class="empty">${escapeHtml(c.empty)}</p>`) +
          `</div></section>`
        );
      }
      booksEl.innerHTML = blocks.join("");
    } catch (e) {
      booksEl.innerHTML = `<p class="empty">${escapeHtml(c.fail)}</p>`;
    }
  }

  function cardHtml(b, c) {
    return (
      `<article class="book-card" draggable="true" data-book-id="${escapeHtml(b.id)}">` +
      `<button type="button" class="icon-del" data-del="${escapeHtml(b.id)}" aria-label="${escapeHtml(c.del)}">×</button>` +
      `<a href="${escapeHtml(b.href)}"><small>${b.units} ${escapeHtml(c.items)}</small>` +
      `<h3>${escapeHtml(b.title)}</h3></a>` +
      `</article>`
    );
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || t().fail);
    return data;
  }

  newFolderBtn.addEventListener("click", async () => {
    const name = window.prompt(t().folderName);
    if (!name) return;
    try {
      await postJson("/api/folder", { name });
      await loadBooks();
    } catch (e) {
      statusEl.textContent = e.message;
    }
  });
  booksEl.addEventListener("click", async (e) => {
    const delBook = e.target.closest("[data-del]");
    const delFolder = e.target.closest("[data-del-folder]");
    if (delBook || delFolder) e.preventDefault();
    try {
      if (delBook) {
        if (!window.confirm(t().confirmDel)) return;
        await postJson("/api/delete", { id: delBook.getAttribute("data-del") });
        await loadBooks();
      }
      if (delFolder) {
        if (!window.confirm(t().confirmFolder)) return;
        await postJson("/api/delete", { id: delFolder.getAttribute("data-del-folder") });
        await loadBooks();
      }
    } catch (err) {
      statusEl.textContent = err.message;
    }
  });
  booksEl.addEventListener("dragstart", (e) => {
    const card = e.target.closest("[data-book-id]");
    if (!card || e.target.closest(".icon-del")) return;
    e.dataTransfer.setData("text/plain", card.getAttribute("data-book-id"));
    e.dataTransfer.effectAllowed = "move";
    card.classList.add("dragging");
  });
  booksEl.addEventListener("dragend", (e) => {
    e.target.closest("[data-book-id]")?.classList.remove("dragging");
    booksEl.querySelectorAll(".over").forEach((el) => el.classList.remove("over"));
  });
  booksEl.addEventListener("dragover", (e) => {
    const zone = e.target.closest("[data-drop-folder]");
    if (!zone) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    zone.classList.add("over");
  });
  booksEl.addEventListener("dragleave", (e) => {
    const zone = e.target.closest("[data-drop-folder]");
    if (zone && !zone.contains(e.relatedTarget)) zone.classList.remove("over");
  });
  booksEl.addEventListener("drop", async (e) => {
    const zone = e.target.closest("[data-drop-folder]");
    if (!zone) return;
    e.preventDefault();
    zone.classList.remove("over");
    const id = e.dataTransfer.getData("text/plain");
    if (!id) return;
    try {
      await postJson("/api/move", { id, folder: zone.getAttribute("data-drop-folder") || "" });
      await loadBooks();
    } catch (err) {
      statusEl.textContent = err.message;
    }
  });

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

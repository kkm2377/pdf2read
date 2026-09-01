from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pdf2read.convert import convert_book

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_UPLOAD = 80 * 1024 * 1024
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def slugify(title: str, stem: str) -> str:
    raw = re.sub(r"[^\w\-]+", "-", title, flags=re.UNICODE)
    raw = re.sub(r"-{2,}", "-", raw).strip("-").lower()
    ascii_only = re.sub(r"[^a-z0-9\-]+", "", raw)
    base = ascii_only[:32] or re.sub(r"[^a-z0-9\-]+", "-", stem.lower())[:32] or "book"
    return base.strip("-") or "book"


SKIP_NAMES = {".incoming", "__pycache__", ".DS_Store"}


def safe_rel(root: Path, rel: str) -> Path:
    rel = (rel or "").replace("\\", "/").strip("/")
    root_r = root.resolve()
    if not rel:
        return root_r
    parts = Path(rel).parts
    if ".." in parts or any(p.startswith(".") for p in parts):
        raise ValueError("invalid path")
    path = (root / rel).resolve()
    path.relative_to(root_r)
    return path


def is_book_dir(path: Path) -> bool:
    return (path / "viewer" / "nav-data.js").exists()


def _book_info(root: Path, book: Path) -> dict:
    rel = book.relative_to(root).as_posix()
    folder = "" if book.parent == root else book.parent.relative_to(root).as_posix()
    title = book.name
    units = 0
    nav = book / "viewer" / "nav-data.js"
    try:
        text = nav.read_text(encoding="utf-8")
        raw = text.split("=", 1)[1].strip()
        if raw.endswith(";"):
            raw = raw[:-1]
        data = json.loads(raw)
        title = data.get("title") or title
        units = len(data.get("pages") or [])
    except Exception:
        pass
    return {
        "id": rel,
        "title": title,
        "href": f"/{rel}/index.html",
        "units": units,
        "folder": folder,
        "mtime": int(book.stat().st_mtime),
    }


def list_library(root: Path) -> dict:
    root = root.resolve()
    books = []
    folders = []
    if not root.exists():
        return {"books": [], "folders": []}
    for nav in root.rglob("nav-data.js"):
        if nav.parent.name != "viewer":
            continue
        book = nav.parent.parent
        try:
            book.relative_to(root)
        except ValueError:
            continue
        if book == root or not book.is_dir():
            continue
        books.append(_book_info(root, book))
    seen = {b["folder"] for b in books if b["folder"]}
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in SKIP_NAMES or child.name.startswith("."):
            continue
        if is_book_dir(child):
            continue
        seen.add(child.name)
    folders = [{"id": name, "name": name} for name in sorted(seen)]
    books.sort(key=lambda b: (-b["mtime"], b["id"]))
    return {"books": books, "folders": folders}


def unique_dest(folder: Path, name: str) -> Path:
    dest = folder / name
    n = 2
    while dest.exists():
        dest = folder / f"{name}-{n}"
        n += 1
    return dest


def _parse_multipart(handler: SimpleHTTPRequestHandler) -> tuple[dict, dict]:
    ctype = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length") or 0)
    if length > MAX_UPLOAD:
        raise ValueError("file too large")
    body = handler.rfile.read(length)
    msg = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + body
    )
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    parts = msg.iter_parts() if msg.is_multipart() else []
    for part in parts:
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if filename:
            files[name] = (filename, payload or b"")
        else:
            if payload is None:
                fields[name] = ""
            else:
                fields[name] = payload.decode("utf-8", "replace")
    return fields, files


def make_handler(root: Path):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, fmt, *rest):
            print(fmt % rest, flush=True)

        def _json(self, code: int, data: dict):
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_file(self, path: Path, content_type: str):
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path in {"/", "/index.html"}:
                self._send_file(WEB_DIR / "library.html", "text/html; charset=utf-8")
                return
            if path == "/app/library.css":
                self._send_file(WEB_DIR / "library.css", "text/css; charset=utf-8")
                return
            if path == "/app/library.js":
                self._send_file(WEB_DIR / "library.js", "text/javascript; charset=utf-8")
                return
            if path == "/api/books":
                self._json(200, list_library(root))
                return
            if path.startswith("/api/jobs/"):
                job_id = path.rsplit("/", 1)[-1]
                with JOBS_LOCK:
                    job = JOBS.get(job_id)
                if not job:
                    self._json(404, {"error": "job not found"})
                    return
                self._json(200, job)
                return
            return super().do_GET()

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                raise ValueError("too large")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/convert":
                return self._convert()
            if path == "/api/folder":
                return self._folder()
            if path == "/api/move":
                return self._move()
            if path == "/api/delete":
                return self._delete()
            if path == "/api/reveal":
                return self._reveal()
            self._json(404, {"error": "not found"})

        def _convert(self):
            try:
                fields, files = _parse_multipart(self)
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
            if "pdf" not in files:
                self._json(400, {"error": "PDF 파일을 선택해 주세요."})
                return
            filename, data = files["pdf"]
            if not filename.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
                self._json(400, {"error": "PDF만 올릴 수 있습니다."})
                return
            lang = (fields.get("lang") or "auto").strip() or "auto"
            ui_lang = (fields.get("ui_lang") or "ko").strip() or "ko"
            if ui_lang not in {"ko", "en", "ja"}:
                ui_lang = "ko"
            folder = (fields.get("folder") or "").strip()
            job_id = uuid.uuid4().hex[:12]
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "id": job_id,
                    "status": "queued",
                    "log": [],
                    "href": None,
                    "title": filename,
                    "error": None,
                }
            threading.Thread(
                target=_run_job,
                args=(root, job_id, filename, data, lang, ui_lang, folder),
                daemon=True,
            ).start()
            self._json(202, {"id": job_id})

        def _folder(self):
            try:
                data = self._read_json()
                name = re.sub(r"[\\/]+", "-", str(data.get("name") or "")).strip()
                if not name or name in {".", ".."} or name.startswith("."):
                    raise ValueError("폴더 이름을 넣어 주세요.")
                dest = unique_dest(root, name[:40])
                dest.mkdir(parents=True, exist_ok=False)
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
            except FileExistsError:
                self._json(400, {"error": "같은 이름 폴더가 있습니다."})
                return
            self._json(200, list_library(root))

        def _move(self):
            try:
                data = self._read_json()
                src = safe_rel(root, str(data.get("id") or ""))
                folder = str(data.get("folder") or "").strip()
                if src == root or not is_book_dir(src):
                    raise ValueError("책을 찾을 수 없습니다.")
                dest_dir = root if not folder else safe_rel(root, folder)
                if dest_dir != root and is_book_dir(dest_dir):
                    raise ValueError("책 안으로 옮길 수 없습니다.")
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = unique_dest(dest_dir, src.name)
                shutil.move(str(src), str(dest))
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
            self._json(200, list_library(root))

        def _delete(self):
            try:
                data = self._read_json()
                target = safe_rel(root, str(data.get("id") or ""))
                if target == root:
                    raise ValueError("서재 전체는 지울 수 없습니다.")
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.is_file():
                    target.unlink()
                else:
                    raise ValueError("찾을 수 없습니다.")
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
            self._json(200, list_library(root))

        def _reveal(self):
            try:
                data = self._read_json()
                target = safe_rel(root, str(data.get("id") or ""))
                if not target.exists():
                    target = root
                subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                self._json(400, {"error": "폴더를 열 수 없습니다."})
                return
            self._json(200, {"ok": True})

    return Handler


def _run_job(root: Path, job_id: str, filename: str, data: bytes, lang: str, ui_lang: str, folder: str = "") -> None:
    def log(msg: str):
        with JOBS_LOCK:
            JOBS[job_id]["log"].append(msg)
            JOBS[job_id]["status"] = "running"

    incoming = root / ".incoming"
    incoming.mkdir(exist_ok=True)
    src = incoming / f"{job_id}.pdf"
    src.write_bytes(data)
    stem = Path(filename).stem
    slug = slugify(stem, stem)
    try:
        parent = root if not folder else safe_rel(root, folder)
        parent.mkdir(parents=True, exist_ok=True)
        dest = unique_dest(parent, slug)
    except ValueError as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
        return
    try:
        log(f"{filename} 변환을 시작합니다.")
        result = convert_book(
            src,
            dest,
            lang=lang,
            ui_lang=ui_lang,
            show_library=True,
            progress=log,
        )
        rel = dest.relative_to(root.resolve()).as_posix()
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["href"] = f"/{rel}/index.html"
            JOBS[job_id]["title"] = result["title"]
    except Exception as e:
        shutil.rmtree(dest, ignore_errors=True)
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
            JOBS[job_id]["log"].append(f"실패: {e}")
    finally:
        try:
            src.unlink(missing_ok=True)
        except OSError:
            pass


class Server(ThreadingHTTPServer):
    allow_reuse_address = True


def serve_library(root: Path, port: int, open_browser: bool = True, host: str = "127.0.0.1") -> int:
    handler = make_handler(root)
    server = Server((host, port), handler)
    url = f"http://{host}:{port}/"
    print(url, flush=True)
    print(f"library: {root}", flush=True)
    if host not in {"127.0.0.1", "localhost"}:
        print("같은 Wi-Fi 또는 Tailscale 주소로 태블릿에서 여세요.", flush=True)
    if open_browser:
        def _open():
            time.sleep(0.4)
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0

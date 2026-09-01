from __future__ import annotations

import json
import re
import shutil
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


def list_books(root: Path) -> list[dict]:
    books = []
    if not root.exists():
        return books
    for p in sorted(root.iterdir()):
        nav = p / "viewer" / "nav-data.js"
        if not p.is_dir() or not nav.exists():
            continue
        title = p.name
        units = 0
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
        books.append({
            "id": p.name,
            "title": title,
            "href": f"/{p.name}/index.html",
            "units": units,
            "mtime": int(p.stat().st_mtime),
        })
    books.sort(key=lambda b: b["mtime"], reverse=True)
    return books


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
                self._json(200, {"books": list_books(root)})
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

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/api/convert":
                self._json(404, {"error": "not found"})
                return
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
            thread = threading.Thread(
                target=_run_job,
                args=(root, job_id, filename, data, lang, ui_lang),
                daemon=True,
            )
            thread.start()
            self._json(202, {"id": job_id})

    return Handler


def _run_job(root: Path, job_id: str, filename: str, data: bytes, lang: str, ui_lang: str) -> None:
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
    dest = root / slug
    n = 2
    while dest.exists():
        dest = root / f"{slug}-{n}"
        n += 1
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
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["href"] = f"/{dest.name}/index.html"
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


def serve_library(root: Path, port: int, open_browser: bool = True) -> int:
    handler = make_handler(root)
    server = Server(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(url, flush=True)
    print(f"library: {root}", flush=True)
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

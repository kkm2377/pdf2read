from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import platform
import shutil
import sys
from pathlib import Path

from pdf2read.convert import convert_book
from pdf2read.render import UI
from pdf2read.server import serve_library


def cmd_convert(args: argparse.Namespace) -> int:
    def log(msg: str) -> None:
        print(msg, flush=True)

    result = convert_book(
        args.pdf,
        args.out,
        lang=args.lang,
        ui_lang=args.ui_lang,
        start=args.start,
        end=args.end,
        chunk=args.chunk,
        show_library=args.library,
        profile=args.profile,
        ocr=args.ocr,
        ocr_languages=args.ocr_languages,
        page_images=args.page_images,
        confidence_threshold=args.confidence_threshold,
        cache=not args.no_cache,
        max_engine_pages=args.max_engine_pages,
        progress=log,
    )
    if args.serve:
        root = Path(args.out).expanduser().resolve()
        if args.library:
            return serve_library(
                root.parent,
                args.port,
                open_browser=not args.no_open,
                host=args.host,
                allow_remote_write=args.allow_remote_write,
            )
        return _serve_book(root, args.port, host=args.host)
    print(f"Open with: python -m pdf2read app --dir {Path(args.out).parent} --port {args.port}")
    print(f"  or a single book: python -m pdf2read serve {result['out']} --port {args.port}")
    return 0


def _serve_book(root: Path, port: int, host: str = "127.0.0.1") -> int:
    import os
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    os.chdir(root)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *rest):
            print(fmt % rest, flush=True)

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True

    with Server((host, port), Handler) as httpd:
        print(f"http://{host}:{port}/", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Not found: {root}")
    book_like = (root / "viewer" / "nav-data.js").exists()
    if book_like and not args.app:
        if not (root / "index.html").exists():
            raise SystemExit(f"No index.html in {root}")
        return _serve_book(root, args.port, host=args.host)
    return serve_library(
        root,
        args.port,
        open_browser=not args.no_open,
        host=args.host,
        allow_remote_write=args.allow_remote_write,
    )


def cmd_app(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return serve_library(
        root,
        args.port,
        open_browser=not args.no_open,
        host=args.host,
        allow_remote_write=args.allow_remote_write,
    )


def _package_version(*names: str) -> str | None:
    for name in names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def cmd_doctor(_args: argparse.Namespace) -> int:
    rapid_version = _package_version("rapidocr")
    onnx_version = _package_version("onnxruntime", "onnxruntime-gpu")
    rapid_ready = (
        importlib.util.find_spec("rapidocr") is not None
        and importlib.util.find_spec("onnxruntime") is not None
    )
    checks = [
        ("Python", platform.python_version(), True),
        ("PyMuPDF", _package_version("PyMuPDF", "pymupdf") or "missing", importlib.util.find_spec("pymupdf") is not None),
        (
            "Docling",
            _package_version("docling-slim", "docling") or "not installed",
            importlib.util.find_spec("docling") is not None,
        ),
        (
            "macOS OCR",
            _package_version("ocrmac") or ("not applicable" if sys.platform != "darwin" else "not installed"),
            sys.platform != "darwin" or importlib.util.find_spec("ocrmac") is not None,
        ),
        (
            "RapidOCR",
            (
                f"{rapid_version or 'missing'} · ONNX {onnx_version or 'missing'}"
            ),
            rapid_ready,
        ),
        ("OCRmyPDF", shutil.which("ocrmypdf") or "not installed", shutil.which("ocrmypdf") is not None),
    ]
    print(f"pdf2read doctor · {platform.system()} {platform.machine()}")
    for name, detail, available in checks:
        mark = "OK" if available else "--"
        print(f"[{mark}] {name}: {detail}")
    if importlib.util.find_spec("docling") is None:
        print('\n균형형 설치: pip install -e ".[quality]"')
    if shutil.which("ocrmypdf") is None:
        if sys.platform == "darwin":
            print("스캔 전처리(선택): brew install ocrmypdf tesseract-lang")
        else:
            print('스캔 전처리(선택): pip install -e ".[ocr]" + OS의 Tesseract/Ghostscript')
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="pdf2read",
        description="Convert a selectable-text PDF into a readable HTML viewer",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="Convert a PDF to an HTML viewer")
    c.add_argument("pdf")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--lang", default="auto", help="Source language, or auto")
    c.add_argument("--ui-lang", default="ko", choices=sorted(UI))
    c.add_argument("--start", type=int, default=None)
    c.add_argument("--end", type=int, default=None)
    c.add_argument("--chunk", type=int, default=8, help="Pages per unit when the PDF has no outline")
    c.add_argument("--library", action="store_true", help="Add a back-link to the parent library")
    c.add_argument("--profile", default="balanced", choices=["auto", "fast", "balanced"])
    c.add_argument("--ocr", default="auto", choices=["auto", "off", "ocrmypdf"])
    c.add_argument("--ocr-languages", default="eng+jpn+kor")
    c.add_argument("--page-images", default="auto", choices=["auto", "always", "never"])
    c.add_argument("--confidence-threshold", type=float, default=0.62)
    c.add_argument("--max-engine-pages", type=int, default=80)
    c.add_argument("--no-cache", action="store_true")
    c.add_argument("--serve", action="store_true")
    c.add_argument("--port", type=int, default=8770)
    c.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for tablet/LAN")
    c.add_argument("--allow-remote-write", action="store_true", help="Allow remote convert/move/delete (unsafe)")
    c.add_argument("--no-open", action="store_true")
    c.set_defaults(func=cmd_convert)

    s = sub.add_parser("serve", help="Serve a converted book, or a library folder")
    s.add_argument("dir")
    s.add_argument("--port", type=int, default=8770)
    s.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for tablet/LAN")
    s.add_argument("--allow-remote-write", action="store_true", help="Allow remote convert/move/delete (unsafe)")
    s.add_argument("--app", action="store_true", help="Force library + upload UI")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(func=cmd_serve)

    a = sub.add_parser("app", help="Open the library landing page and convert PDFs in the browser")
    a.add_argument("--dir", default="out", help="Folder of converted books")
    a.add_argument("--port", type=int, default=8770)
    a.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for tablet/LAN")
    a.add_argument("--allow-remote-write", action="store_true", help="Allow remote convert/move/delete (unsafe)")
    a.add_argument("--no-open", action="store_true")
    a.set_defaults(func=cmd_app)

    d = sub.add_parser("doctor", help="Check optional layout/OCR engines")
    d.set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

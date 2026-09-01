from __future__ import annotations

import argparse
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
        progress=log,
    )
    if args.serve:
        root = Path(args.out).expanduser().resolve()
        if args.library:
            return serve_library(root.parent, args.port, open_browser=not args.no_open)
        return _serve_book(root, args.port)
    print(f"Open with: python -m pdf2read app --dir {Path(args.out).parent} --port {args.port}")
    print(f"  or a single book: python -m pdf2read serve {result['out']} --port {args.port}")
    return 0


def _serve_book(root: Path, port: int) -> int:
    import os
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    os.chdir(root)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *rest):
            print(fmt % rest, flush=True)

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True

    with Server(("127.0.0.1", port), Handler) as httpd:
        print(f"http://127.0.0.1:{port}/", flush=True)
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
        return _serve_book(root, args.port)
    return serve_library(root, args.port, open_browser=not args.no_open)


def cmd_app(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return serve_library(root, args.port, open_browser=not args.no_open)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="pdf2read",
        description="PDF textbook → HTML viewer you can translate in Chrome",
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
    c.add_argument("--serve", action="store_true")
    c.add_argument("--port", type=int, default=8770)
    c.add_argument("--no-open", action="store_true")
    c.set_defaults(func=cmd_convert)

    s = sub.add_parser("serve", help="Serve a converted book, or a library folder")
    s.add_argument("dir")
    s.add_argument("--port", type=int, default=8770)
    s.add_argument("--app", action="store_true", help="Force library + upload UI")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(func=cmd_serve)

    a = sub.add_parser("app", help="Open the library landing page and convert PDFs in the browser")
    a.add_argument("--dir", default="out", help="Folder of converted books")
    a.add_argument("--port", type=int, default=8770)
    a.add_argument("--no-open", action="store_true")
    a.set_defaults(func=cmd_app)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

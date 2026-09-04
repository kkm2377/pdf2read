import json
import threading
from http.client import HTTPConnection
from pathlib import Path

from pdf2read.server import Server, _can_write, _safe_static_target, make_handler


def test_remote_clients_are_read_only_by_default():
    assert _can_write("127.0.0.1", False)
    assert _can_write("::1", False)
    assert not _can_write("192.168.0.20", False)
    assert not _can_write("100.64.0.10", False)
    assert _can_write("192.168.0.20", True)


def test_static_files_cannot_escape_or_expose_hidden_paths(tmp_path: Path):
    public = tmp_path / "book.html"
    hidden = tmp_path / ".incoming" / "source.pdf"
    outside = tmp_path.parent / "secret.pdf"
    public.write_text("book", encoding="utf-8")
    hidden.parent.mkdir()
    hidden.write_text("pdf", encoding="utf-8")

    assert _safe_static_target(tmp_path, str(public))
    assert not _safe_static_target(tmp_path, str(hidden))
    assert not _safe_static_target(tmp_path, str(outside))


def test_library_http_hides_incoming_pdf(tmp_path: Path):
    incoming = tmp_path / ".incoming"
    incoming.mkdir()
    (incoming / "source.pdf").write_bytes(b"%PDF-secret")

    server = Server(("127.0.0.1", 0), make_handler(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        conn.request("GET", "/api/books")
        response = conn.getresponse()
        data = json.loads(response.read())
        assert response.status == 200
        assert data["writable"] is True

        conn.request("GET", "/.incoming/source.pdf")
        response = conn.getresponse()
        response.read()
        assert response.status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_remote_http_cannot_create_folder(tmp_path: Path):
    handler = make_handler(tmp_path)
    handler._request_can_write = lambda self: False
    server = Server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        conn.request("GET", "/api/books")
        response = conn.getresponse()
        data = json.loads(response.read())
        assert response.status == 200
        assert data["writable"] is False

        body = json.dumps({"name": "must-not-create"}).encode()
        conn.request(
            "POST",
            "/api/folder",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        response = conn.getresponse()
        error = json.loads(response.read())
        assert response.status == 403
        assert "읽기만" in error["error"]
        assert not (tmp_path / "must-not-create").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

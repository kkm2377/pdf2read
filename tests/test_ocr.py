from pathlib import Path

from pdf2read.cli import main
from pdf2read.engines.ocr import preprocess_with_ocrmypdf


def test_doctor_command_runs(capsys):
    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "pdf2read doctor" in output
    assert "PyMuPDF" in output
    assert "Docling" in output


def test_ocrmypdf_preprocessor_builds_safe_command(tmp_path: Path, monkeypatch):
    source = tmp_path / "input.pdf"
    destination = tmp_path / "work" / "ocr.pdf"
    source.write_bytes(b"%PDF-test")
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        Path(command[-1]).write_bytes(b"%PDF-ocr")

    monkeypatch.setattr("pdf2read.engines.ocr.ocrmypdf_available", lambda: True)
    monkeypatch.setattr("pdf2read.engines.ocr.subprocess.run", fake_run)
    assert preprocess_with_ocrmypdf(
        source,
        destination,
        languages="eng+jpn",
    )
    assert seen["command"][-2:] == [str(source), str(destination)]
    assert "eng+jpn" in seen["command"]


def test_ocrmypdf_missing_is_nonfatal(tmp_path: Path, monkeypatch):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-test")
    monkeypatch.setattr("pdf2read.engines.ocr.ocrmypdf_available", lambda: False)
    assert not preprocess_with_ocrmypdf(source, tmp_path / "ocr.pdf")

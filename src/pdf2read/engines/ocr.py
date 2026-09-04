from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ocrmypdf_available() -> bool:
    return shutil.which("ocrmypdf") is not None


def preprocess_with_ocrmypdf(
    source: Path,
    destination: Path,
    *,
    languages: str = "eng+jpn+kor",
    log=None,
) -> bool:
    logger = log or (lambda _message: None)
    if not ocrmypdf_available():
        logger("  OCRmyPDF 미설치: 원본 PDF로 계속합니다.")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ocrmypdf",
        "--mode",
        "skip",
        "--rotate-pages",
        "--deskew",
        "--optimize",
        "1",
        "--language",
        languages,
        str(source),
        str(destination),
    ]
    logger(f"  OCRmyPDF 전처리 ({languages})")
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return destination.exists()
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        logger(f"  OCRmyPDF 실패: {detail.strip()[-240:]}")
        return False

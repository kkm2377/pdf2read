# pdf2read

선택 가능한 텍스트 PDF를 읽기 좋은 HTML 뷰어로 바꿉니다.

본문은 원문 HTML로 유지하고 색, 2단 측주, 표, 그림을 PDF에서 가져옵니다.
일반 페이지는 PyMuPDF로 빠르게 처리하고, 선택 설치한 Docling이 있으면 복잡하거나
스캔된 페이지만 구조 분석·OCR로 다시 처리합니다. 그래도 신뢰도가 낮은 페이지는
HTML 안에서 원본 페이지를 바로 펼쳐 볼 수 있습니다.

로컬에서만 동작합니다. 올린 PDF는 바깥 서버로 나가지 않습니다.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.11+가 필요합니다.

가벼운 기본 설치는 PyMuPDF만 사용합니다. Apple Silicon 16GB 이상에서는 균형형 설치를
권장합니다. Docling 모델은 첫 변환 때 한 번 다운로드되고 이후 로컬 캐시에서 실행됩니다.

```bash
pip install -e ".[quality]"
python -m pdf2read doctor
```

회전·기울기 보정이 필요한 스캔 PDF를 OCRmyPDF로 먼저 정리하려면 선택적으로 설치합니다.

```bash
# macOS
brew install ocrmypdf tesseract-lang

# Linux: 배포판의 Tesseract/Ghostscript를 설치한 뒤
pip install -e ".[ocr]"

python -m pdf2read doctor
```

## 앱으로 쓰기

```bash
python -m pdf2read app --dir out --port 8770
```

브라우저에서 http://127.0.0.1:8770/ 이 열립니다. PDF를 놓고 **변환**을 누르면 HTML 뷰어가 됩니다. 원문 언어는 PDF에서 추정합니다. 오른쪽 위에서 화면 언어와 라이트/다크를 바꿀 수 있습니다.

태블릿·다른 기기에서 열려면 `--host 0.0.0.0` 이 필요합니다. 맥 미니에서 상시 켜 두는 절차는 [MACMINI.md](MACMINI.md) 입니다.

```bash
python -m pdf2read app --dir out --port 8770 --host 0.0.0.0 --no-open
```

이렇게 열면 맥 자체의 `127.0.0.1` 접속에서만 변환·이동·삭제가 가능하고,
LAN/Tailscale로 접속한 태블릿은 자동으로 읽기 전용이 됩니다.

## 명령줄

```bash
python -m pdf2read convert book.pdf -o out/book
python -m pdf2read serve out/book --port 8770
```

옵션:

- `--lang` 원문 언어. 기본 `auto`; 순수 이미지 스캔은 서재 옵션에서 직접 선택 권장
- `--ui-lang` 안내 문구 `ko` / `en` / `ja`
- `--start` `--end` 페이지 범위
- `--chunk` 북마크가 없을 때 몇 쪽을 한 항목으로 묶을지
- `--library` 서재로 돌아가는 링크를 뷰어에 넣습니다
- `--profile` `balanced`(기본) / `auto` / `fast`
- `--ocr` `auto`(Docling OCR) / `off` / `ocrmypdf`
- `--ocr-languages` OCRmyPDF 언어. 기본 `eng+jpn+kor`
- `--page-images` `auto`(저신뢰만) / `always` / `never`
- `--confidence-threshold` Docling·원본 보기로 넘길 기준. 기본 `0.62`
- `--max-engine-pages` 한 문서에서 Docling이 처리할 최대 페이지. 기본 `80`
- `--no-cache` Docling 페이지 캐시를 사용하지 않음
- `--host` 서버가 듣는 주소. 기본 `127.0.0.1`(이 컴퓨터만). 태블릿은 `0.0.0.0`
- `--allow-remote-write` 원격 기기에도 변환·이동·삭제 허용. 안전상 권장하지 않음

예:

```bash
python -m pdf2read convert scan.pdf -o out/scan \
  --profile balanced --ocr auto --page-images auto --library

python -m pdf2read convert tilted-scan.pdf -o out/scan \
  --profile balanced --ocr ocrmypdf --ocr-languages eng+jpn+kor
```

## 다른 프로그램에서

```python
from pdf2read import convert_book

result = convert_book(
    "book.pdf",
    "out/book",
    profile="balanced",
    ocr="auto",
    page_images="auto",
)
print(result["title"], result["units"], result["out"])
```

`convert_book`은 출력 폴더, 목차 방식(`outline` / `visual` / `chunks`), 규칙·Docling·
원본 이미지 페이지 수와 캐시 적중 수를 담은 dict를 돌려줍니다.

## 처리 방식

- 선택 가능한 일반 PDF: 내장 규칙 엔진으로 빠르게 변환
- 복잡한 표·다단·스캔 페이지: `[quality]` 설치 시 Docling으로 선택 처리
- 이미지 스캔: macOS OCR 또는 RapidOCR, 선택적으로 OCRmyPDF 전처리
- 저신뢰 페이지: `원본 페이지 보기`가 자동 생성되어 PDF를 따로 열 필요 없음
- 변환 품질 기록: 각 책의 `viewer/quality.json`

세로쓰기, 손상되거나 암호화된 PDF, 매우 복잡한 잡지형 문서는 원본 보기가 붙을 수
있습니다. 모든 페이지를 원본으로 보존하려면 `--page-images always`를 사용합니다.

## 품질 테스트

저작권 있는 교재는 저장소에 넣지 않습니다. 테스트는 직접 생성한 스캔·다단·표·수식·
그림·시험문제·세로쓰기·암호화 PDF를 사용합니다.

```bash
pip install -e ".[dev]"
pytest -q -m "not slow and not needs_model"
pytest tests/quality -q -m "not needs_model and not slow"
python scripts/bench_convert.py --pages 200
```

Docling 모델 테스트는 GitHub Actions의 `quality` workflow를 수동 실행할 때
`run_models`를 켜서 실행합니다.

## 오픈소스 구성

- PyMuPDF: 기본 PDF 읽기·이미지 생성
- Docling 2.x(MIT): 복잡한 레이아웃·표·OCR 구조 분석
- RapidOCR: macOS가 아닌 환경의 기본 Docling OCR
- ocrmac: macOS Vision 기반 OCR
- OCRmyPDF 17.x(MPL-2.0): 선택적 회전·기울기 보정 전처리

텍스트가 전혀 없는 스캔은 언어를 자동 판별할 근거가 없습니다. macOS는 다국어 OCR을
시도하지만 RapidOCR 환경에서는 서재의 `원문 언어` 또는 CLI `--lang`을 반드시
`ja`, `ko`, `en`, `zh` 중 하나로 지정하세요.

## GitHub에 올릴 때

이 저장소에는 **변환기 코드만** 올리는 것이 좋습니다.

- `out/` 변환 결과, 원본 PDF, 시험 교재는 올리지 마세요. (저작권)
- 라이선스는 MIT입니다. 다른 프로그램에서 `convert_book()`을 불러 쓰면 됩니다.
- 호스팅 SaaS가 아니라, 각자 컴퓨터에서 돌리는 도구입니다.

## 구성

- `src/pdf2read/convert.py` 변환 API
- `src/pdf2read/extract.py` 본문·표·그림·콜아웃
- `src/pdf2read/viewer/` 책 뷰어
- `src/pdf2read/web/` 대문(서재) 페이지

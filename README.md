# pdf2read

선택 가능한 텍스트 PDF를 읽기 좋은 HTML 뷰어로 바꿉니다.

본문은 원문 HTML로 유지하고 색, 2단 측주, 표, 그림을 PDF에서 가져옵니다.

로컬에서만 동작합니다. 올린 PDF는 바깥 서버로 나가지 않습니다.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.11+, 의존성은 PyMuPDF 하나입니다.

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

- `--lang` HTML에 기록할 원문 언어. 기본 `auto` (글자에서 추정)
- `--ui-lang` 안내 문구 `ko` / `en` / `ja`
- `--start` `--end` 페이지 범위
- `--chunk` 북마크가 없을 때 몇 쪽을 한 항목으로 묶을지
- `--library` 서재로 돌아가는 링크를 뷰어에 넣습니다
- `--host` 서버가 듣는 주소. 기본 `127.0.0.1`(이 컴퓨터만). 태블릿은 `0.0.0.0`
- `--allow-remote-write` 원격 기기에도 변환·이동·삭제 허용. 안전상 권장하지 않음

## 다른 프로그램에서

```python
from pdf2read import convert_book

result = convert_book("book.pdf", "out/book")
print(result["title"], result["units"], result["out"])
```

`convert_book`은 출력 폴더 경로와 목차 방식(`outline` / `visual` / `chunks`)을 담은 dict를 돌려줍니다.

## 잘 되는 PDF / 아직인 PDF

| 잘 되는 편 | 아직 |
|---|---|
| 글자를 선택할 수 있는 교과서·문제집 | 스캔 이미지만 있는 PDF (OCR 없음) |
| PDF 북마크가 있는 책 | 잡지처럼 레이아웃이 매우 복잡한 것 |
| 본문+측주 2단 | 그림 속 글자를 HTML 텍스트로 추출 |

시험 문제처럼 `問` 옆에 큰 숫자가 있는 레이아웃은 문항 카드로 묶으려 합니다. 모든 출판사 스타일을 맞추지는 않습니다.

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

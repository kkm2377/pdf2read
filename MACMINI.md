# 맥 미니 에이전트용 설정

이 문서는 **맥 미니의 AI 에이전트**가 그대로 실행하면 되도록 쓴 지시입니다. 목표는 맥 미니에서 pdf2read 서재를 켜 두고, 안드로이드 태블릿 Chrome으로 집·밖에서 교과서를 읽는 것입니다.

코드를 고치지 마세요. 이 저장소 `main`을 받아 설치하고, 로컬에서 서버만 켜면 됩니다.

## 하지 말 것

- `out/`, 원본 PDF, 시험 교재를 git에 커밋·푸시하지 말 것 (저작권)
- GitHub Pages 등 공개 호스팅에 변환 HTML을 올리지 말 것
- 공유기 포트포워드(외부에 8770 열기)는 하지 말 것. 집 밖 접속은 Tailscale만 사용
- `file://` 로 HTML을 열지 말 것. 서재 이동과 상대 경로가 불안정함

## 1. 코드 받기

Python 3.11 이상이 필요합니다.

```bash
# 이미 클론되어 있으면
cd ~/원하는경로/pdf2read
git checkout main
git pull origin main

# 처음이면
git clone https://github.com/kkm2377/pdf2read.git
cd pdf2read
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[quality]"
python -m pdf2read doctor
```

`Docling: OK`와 `macOS OCR: OK`인지 확인하세요. Docling 모델은 첫 변환 때 다운로드되므로
처음 한 번은 인터넷과 시간이 필요합니다. 이후에는 로컬 캐시로 실행됩니다.

기울어진 스캔 PDF 전처리도 사용할 경우:

```bash
brew install ocrmypdf tesseract-lang
python -m pdf2read doctor
```

변환 결과(`out/`)는 git에 없습니다. 아래 2-A 또는 2-B 중 하나로 책을 준비하세요.

## 2-A. 이미 변환된 서재가 다른 Mac에 있을 때 (권장)

개발 Mac의 `pdf2read/out/` 폴더 전체를 맥 미니의 같은 위치(`pdf2read/out/`)로 복사합니다. USB, AirDrop, Finder 공유, `rsync` 모두 됩니다.

복사 후 `out/` 안에 책 폴더와 그 안의 `index.html`, `viewer/` 가 있는지 확인하세요.

## 2-B. 맥 미니에 PDF만 있을 때

서재 폴더는 `out/` 입니다. PDF 경로만 바꿔 변환합니다.

```bash
source .venv/bin/activate
python -m pdf2read convert /절대경로/교과서.pdf -o out/sg \
  --profile balanced --ocr auto --page-images auto --ui-lang ko --library
```

여러 권이면 `-o out/폴더이름` 만 바꿔 반복합니다.
스캔이 기울거나 회전돼 있으면 `--ocr ocrmypdf`를 사용하세요.

## 3. 서버 켜기 (태블릿이 접속하려면 host가 필수)

기본값은 `127.0.0.1` 이라 **맥 미니 자신만** 열 수 있습니다. 태블릿용은 반드시 `--host 0.0.0.0` 입니다.

```bash
cd ~/원하는경로/pdf2read
source .venv/bin/activate
python -m pdf2read app --dir out --port 8770 --host 0.0.0.0 --no-open
```

이 상태에서 맥 미니의 `http://127.0.0.1:8770/`은 변환·폴더 이동·삭제가 가능하고,
태블릿의 LAN/Tailscale 주소는 자동으로 **읽기 전용**이 됩니다. 따라서 태블릿을 분실하거나
같은 Wi-Fi에 다른 사람이 있어도 원격으로 책을 지울 수 없습니다.
`--allow-remote-write`는 특별한 이유가 없는 한 사용하지 마세요.

이 터미널은 끄지 마세요. 맥 미니는 공부하는 동안 잠자기 금지:

- 시스템 설정 → 에너지 → 디스플레이가 꺼져도 잠자지 않기 (또는 `caffeinate`를 서버와 같이 실행)

```bash
caffeinate -s python -m pdf2read app --dir out --port 8770 --host 0.0.0.0 --no-open
```

맥 미니에서 `http://127.0.0.1:8770/` 이 열리는지 먼저 확인합니다.

## 4. 집 안 태블릿

1. 맥 미니와 태블릿이 **같은 Wi-Fi**
2. 맥 미니 LAN IP 확인: 시스템 설정 → 네트워크, 또는 `ipconfig getifaddr en0` (이더넷은 `en1`일 수 있음)
3. 태블릿 **Chrome**에서 `http://그IP:8770/` 을 연다

macOS 방화벽이 켜져 있으면 Python이 8770을 받도록 허용하세요.

## 5. 집 밖 (Tailscale)

공유기 포트포워드 대신 Tailscale을 씁니다.

1. 맥 미니와 안드로이드에 [Tailscale](https://tailscale.com)을 **같은 계정**으로 설치·로그인
2. 맥 미니 Tailscale IP 확인: Tailscale 메뉴, 또는 `tailscale ip -4`
3. 태블릿 Chrome에서 `http://맥미니의TailscaleIPv4:8770/` 을 연다
4. 인터넷만 되면 카페·모바일망에서도 동일

서버는 3번처럼 `--host 0.0.0.0` 으로 켜 둔 상태여야 합니다. `127.0.0.1` 만 듣고 있으면 Tailscale로도 태블릿이 못 들어갑니다.

## 6. 확인 체크리스트

- [ ] `git pull` 한 `main` 이 GitHub와 같음
- [ ] `python -m pdf2read doctor`에서 Docling과 macOS OCR이 `OK`
- [ ] `out/` 에 책이 있고 서재에 보임
- [ ] 맥 미니 브라우저 `http://127.0.0.1:8770/`
- [ ] 같은 Wi-Fi 태블릿 Chrome `http://LAN_IP:8770/` (읽기 전용)
- [ ] Tailscale 설치 후 태블릿 `http://TAILSCALE_IP:8770/` (읽기 전용)
- [ ] PDF·`out/` 을 git에 올리지 않음

끝나면 사용자에게 **LAN 주소**와 **Tailscale 주소** 두 개를 알려 주세요.

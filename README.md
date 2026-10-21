# 사이, 서재

영어 소설 두 권과 사진에서 추출한 포커 전략서를 전자책으로 읽는 웹 서재입니다.

- 웹사이트: https://loong-kid.github.io/sai-library/
- GitHub: https://github.com/Loong-kid/sai-library

## 실행

```powershell
python -m http.server 4173 --directory dist
```

http://localhost:4173 에서 엽니다. 별도의 빌드나 Node 의존성이 없습니다.

## 기능

- 셜록 홈즈 전집 118개 목차 항목, Solo Leveling 201–270화
- 상어책 (Hunter Cichy, Advanced Concepts in No-Limit Hold’em): 촬영본 255쪽, 원문 18–272쪽
- 페이지 넘기기 / 스크롤, 키보드 방향키와 모바일 스와이프
- 낮 / 종이 / 밤 배경, 글자 크기 16–32px, 세리프 / 산세리프
- 목차, 전체 본문 검색, 여러 책갈피
- 읽던 위치와 독서 설정을 브라우저 localStorage에 저장
- 읽던 위치는 기기나 브라우저 사이에서 동기화되지 않음
- 사진 책의 OCR 텍스트 검색, 원본 페이지 확대, 원본에서 해당 쪽으로 이동
- 본문 위치에 표·도표 319개 삽입, 도표 확대와 원본 비교
- 직접 대조한 웹 표 6개와 원형 차트 9개, 범위 차트와 카드 상황 그림의 벡터 도표

## 본문 다시 추출

원본 PDF는 상위 폴더에 그대로 보관합니다. `pip install pymupdf` 후:

```powershell
python scripts/import_books.py
```

셜록 홈즈의 2단 조판을 열 순서로 읽고, PDF 줄바꿈과 분철을 정리합니다. 원문은 추출 과정에서 교정하거나 번역하지 않습니다. 원본 PDF의 복잡한 조판 때문에 일부 문단 경계와 단어 분철이 다를 수 있습니다.

## 상어책 사진에서 다시 추출

원본 사진은 `Downloads/상어책`에 그대로 두며 수정하지 않습니다. 255장의 EXIF `DateTimeOriginal`로 촬영 순서를 정하고, 글줄을 검출한 뒤 각 영역을 바로 펴서 영어 OCR을 수행합니다. 파일 수정 시간은 정렬에 사용하지 않습니다.

준비: Python의 Pillow, numpy, opencv-python, rapidocr-onnxruntime와 영어 모델을 포함한 Tesseract가 필요합니다.

```powershell
python scripts/ocr_photos.py --workers 3
python scripts/refine_photos.py --workers 3
python scripts/extract_figures.py
python scripts/compile_shark.py
```

첫 두 명령은 `artifacts/shark/ocr`에 중간 결과를 저장하므로 재실행 시 완료한 사진을 다시 처리하지 않습니다. 원본 폴더와 Tesseract 경로는 첫 명령의 `--source`, `--tesseract`로 지정할 수 있습니다. 글줄 재인식은 `C:/Program Files/Tesseract-OCR/tesseract.exe`를 사용합니다.

배포에는 EXIF를 제거한 WebP 사진, 추출 텍스트, SVG 도표를 포함합니다. 사진은 원본 보기에서 해당 쪽을 열 때만 불러옵니다. `dist/books/advanced-holdem/sources.json`은 파일명·촬영 시각·쪽수 대조 기록이며 `extracted.txt`는 페이지별 추출 텍스트입니다.

1–17쪽은 원본 사진에 없어 포함하지 않습니다. 본문 OCR과 작은 도표 글자에는 오류가 있을 수 있으므로 각 페이지의 **원본 보기**로 대조합니다. 자동 인식이 특히 고르지 않은 쪽에는 원본 대조 안내를 표시합니다. 18–19쪽의 표와 본문, 48쪽의 문단을 사진과 직접 대조해 교정했습니다. 수동 본문 교정은 `scripts/shark_corrections.json`에 추가할 수 있습니다.

`extract_figures.py`는 255쪽에서 표와 도표를 검출하고 원래 본문 위치를 기록합니다. `scripts/native_figures.json`의 표 6개(18·19·22·183·228쪽)와 원형 차트 9개는 원본 수치·카드 무늬를 직접 대조해 HTML/SVG로 다시 만들었습니다. 나머지 304개는 원본의 선·숫자·카드 모양을 SVG 경로로 옮긴 벡터 도표입니다. 범위 차트의 색은 의미를 바꾸지 않도록 촬영본의 색조를 보존하며, 모든 수치를 별도 데이터로 복원한 것은 아닙니다. 사진에 있던 휘어짐이나 작은 인쇄 흔적은 일부 남을 수 있습니다.

도표에는 외부 이미지나 래스터 사진이 들어 있지 않습니다. `figures/manifest.json`에 추출 영역·변환 방식·쪽수, 장별 JSON에 본문 삽입 위치를 저장합니다. 도표 추출 중간 결과도 캐시하며, 설정을 바꾼 후에는 `python scripts/extract_figures.py --force`를 실행합니다. 도표 안의 버튼으로 확대하고 원본 사진과 비교할 수 있습니다. 웹 표는 본문 검색에서 수치와 카드 표기를 찾을 수 있습니다.

## 배포

GitHub Pages의 공개 사이트입니다. `main`에 push하면 `.github/workflows/pages.yml`이 `dist` 디렉터리를 자동 배포합니다. 저장소 Settings → Pages의 배포 소스는 GitHub Actions입니다.

기존 Sites 배포 설정은 `.openai/hosting.json`에 보관합니다. 원본 PDF는 저장소와 배포에 포함되지 않습니다. Google Fonts를 사용할 수 없는 환경에서는 브라우저 기본 대체 글꼴로 표시합니다.

## 기능 검증

미리보기 서버를 실행한 상태에서:

```powershell
npm.cmd install --prefix artifacts/qa --no-audit --no-fund jsdom
node scripts/verify.mjs
```

GitHub Pages의 하위 경로를 가정하여 리소스 경로와 주요 독서 기능을 DOM에서 검사합니다. 실제 브라우저 레이아웃 검사는 별도로 필요합니다.

Windows에 Chrome이 설치되어 있다면 실제 브라우저에서도 검사할 수 있습니다.

```powershell
npm.cmd install --prefix artifacts/qa --no-audit --no-fund playwright-core
node scripts/verify-browser.mjs
```

PC(1440×1000), 모바일(390×844), 가로 화면(844×390)에서 표의 페이지 내 높이, 도표 이미지 로딩, 확대·원본 비교, 대화상자 범위를 확인합니다. 검증용 스크린샷은 배포하지 않고 `artifacts/qa/screenshots`에 저장합니다.

# 사이, 서재

영어 소설 PDF 두 권을 전자책으로 읽는 웹 서재입니다.

- 웹사이트: https://loong-kid.github.io/sai-library/
- GitHub: https://github.com/Loong-kid/sai-library

## 실행

```powershell
python -m http.server 4173 --directory dist
```

http://localhost:4173 에서 엽니다. 별도의 빌드나 Node 의존성이 없습니다.

## 기능

- 셜록 홈즈 전집 118개 목차 항목, Solo Leveling 201–270화
- 페이지 넘기기 / 스크롤, 키보드 방향키와 모바일 스와이프
- 낮 / 종이 / 밤 배경, 글자 크기 16–32px, 세리프 / 산세리프
- 목차, 전체 본문 검색, 여러 책갈피
- 읽던 위치와 독서 설정을 브라우저 localStorage에 저장
- 읽던 위치는 기기나 브라우저 사이에서 동기화되지 않음

## 본문 다시 추출

원본 PDF는 상위 폴더에 그대로 보관합니다. `pip install pymupdf` 후:

```powershell
python scripts/import_books.py
```

셜록 홈즈의 2단 조판을 열 순서로 읽고, PDF 줄바꿈과 분철을 정리합니다. 원문은 추출 과정에서 교정하거나 번역하지 않습니다. 원본 PDF의 복잡한 조판 때문에 일부 문단 경계와 단어 분철이 다를 수 있습니다.

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

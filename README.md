# GCE Study Desk

Google Certified Educator 학습 문서를 검색하고, 문서에서 찾지 못한 문제는 OpenAI 웹 검색으로 확인하는 웹 앱입니다.

## 선생님들과 웹에서 공동 사용

**GitHub + Vercel**로 배포할 수 있습니다. [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)의 안내에 따라 저장소를 연결하고 접속 비밀번호와 관리자 OpenAI API 키를 환경변수로 입력하세요. 선생님들은 배포된 주소와 비밀번호만 있으면 이용할 수 있습니다.

Vercel에서는 이미지 문자 인식을 브라우저에서 처리하며, 별도 데이터베이스나 Tesseract 서버 설치가 필요하지 않습니다. 관리자 키는 서버에만 보관합니다. 하루 사용 후 자동 종료할 시간을 지정할 수 있습니다. 이 간단한 구성에는 전체 사용자의 일일 API 호출 수를 보장하는 한도 기능이 없습니다.

영구 사용량 저장과 일일 공동 한도가 필요한 별도 구성은 [DEPLOY_RENDER.md](DEPLOY_RENDER.md)에 있습니다.

아래는 개인 컴퓨터에서 사용하는 로컬 모드 설명입니다.

## 실행

Python 3.12 이상과 Tesseract의 영어 언어 데이터가 필요합니다.

두 프로그램을 설치한 뒤 `python run.py`를 실행하면 Python 패키지를 준비하고 브라우저를 엽니다. Windows에서는 `start_windows.bat`를 실행할 수 있습니다. 서버를 종료하려면 실행한 터미널에서 Ctrl+C를 누릅니다.

수동으로 설치 및 실행하려면:

```bash
# Ubuntu / Debian에서 Tesseract가 없다면:
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

cd /path/to/123
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

개인 컴퓨터에서 실행한 서버의 8000번 포트로 브라우저에서 접속합니다. 기본 로컬 모드에는 로그인이 없으므로 공동 사용은 위의 Vercel 배포 안내를 따르세요.

Windows에서는 Python과 Tesseract를 설치하고 Tesseract 실행 파일을 PATH에 추가한 후 `python -m venv .venv`, `.venv\Scripts\python -m pip install -r requirements.txt`, `.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`을 실행합니다. macOS에서는 `brew install tesseract`로 OCR 엔진을 설치할 수 있습니다. Windows/macOS에서의 실행은 아직 검증하지 않았습니다.

## 사용

1. 공동 웹 앱에서는 관리자가 알려준 비밀번호로 로그인합니다. 개인 로컬 모드에서는 앱의 **API 설정**에서 OpenAI API 키를 입력합니다. 기본 모델은 `gpt-4.1-mini`입니다.
2. 문제와 보기가 보이는 이미지를 업로드하거나 붙여넣습니다. 데스크톱 브라우저에서 **화면 캡처**를 선택해 다른 창을 촬영할 수도 있습니다. 캡처 직후 화면 공유를 중지합니다.
3. 영어 OCR 결과로 자동 검색합니다. 다른 언어의 문제는 텍스트를 직접 붙여넣을 수 있습니다. 한 번에 한 문제와 보기만 캡처하면 정확도가 높아집니다.
4. 확실히 일치하는 문서가 없으면 OpenAI 웹 검색을 사용합니다. 문서 답에서도 **웹 출처로 다시 검증**을 누를 수 있습니다.

개인 모드에서 입력한 키는 브라우저 메모리에만 보관하며 새로고침하면 지워집니다. 공동 모드의 키는 서버 환경변수에 보관하며 선생님들에게 전달하지 않습니다. 웹 검색에는 별도 OpenAI API 사용료가 발생합니다. 웹 요청은 문제 텍스트와 상위 문서 후보 두 개를 OpenAI로 전송합니다. Vercel에서는 이미지가 브라우저 안에서 처리되며 서버로 업로드되지 않습니다. 로컬 모드에서는 로컬 Tesseract로 처리하고 임시 파일은 제거합니다. API 요청은 `store: false`로 전송합니다. API 공급자의 별도 데이터 처리 정책은 해당 서비스 정책을 따릅니다.

서버 환경변수 `GCE_OPENAI_API_KEY`를 설정할 수도 있습니다. 키를 코드, 저장소 또는 채팅에 기록하지 마세요. API 요청의 유일한 외부 목적지는 `api.openai.com`입니다.

## 자료 및 정확도

- Level 1: 문제 및 정답 37개, 실습 3개.
- Level 2: 정답 25개. 문제 본문이 없어 자동 매칭에는 사용하지 않습니다.
- Level 1의 1, 4, 6, 9, 10, 23, 26, 27, 29, 31, 33, 34, 37번은 원본 답과 별도로 수정 제안 및 이유를 보존합니다. 이는 편집 검토 결과이며 공식 정답 또는 웹 검증 완료를 뜻하지 않습니다.
- 문서 검색은 영어 원문/OCR 중심의 문자·단어 유사도입니다. 번역되거나 크게 바뀐 문장은 웹 검색으로 넘어갈 수 있습니다. 유사도 수치는 정답 확률이 아닙니다.
- 웹 검색 완료 상태와 HTTPS 출처가 있는 응답만 표시합니다. 모델의 해석은 틀릴 수 있으므로 표시된 근거를 확인할 수 있습니다.

자료는 `data/questions.json`에 포함되어 있어 원본 Word 파일 없이 실행됩니다. 원본 문서로 다시 생성하려면 `python scripts/import_documents.py /path/to/docx-directory`를 실행합니다.

## 검증

```bash
python -m unittest discover -s tests -v
node --check app/static/app.js
node --check app/static/browser-ocr.js
```

테스트는 37개 문제 검색, 보기 순서 변경, OCR 오타, 실제 이미지 OCR→검색, 불일치 처리, 답안만 있는 자료 제외, 웹 API 응답/출처 검증, API 오류 처리, Vercel의 로그인·만료·종료 시간을 확인합니다. 웹 API 테스트는 모의 응답을 사용합니다. 실제 OpenAI 검색 성공 여부는 유효한 키를 입력한 후 별도로 확인해야 합니다.

`tests/browser_vercel.py`는 Playwright, 시스템 Chromium, DejaVu Sans 글꼴이 있는 Linux에서 실행하는 선택적 브라우저 통합 검사입니다. 실제 WebAssembly OCR과 이미지에서 문서 답을 찾는 흐름을 검사합니다.

브라우저 OCR 파일은 `public/vendor/ocr`에 포함되어 있습니다. 파일을 재생성할 때만 `npm ci --ignore-scripts`와 `npm run vendor-ocr`를 실행하세요. `manifest.json`에 버전과 SHA-256을 기록합니다.

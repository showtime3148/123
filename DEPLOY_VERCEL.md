# GitHub + Vercel 배포

하루 동안 선생님들과 함께 사용할 수 있는 구성입니다. 별도 데이터베이스 없이, 접속 비밀번호와 관리자 OpenAI API 키 하나를 사용합니다.

## 1. GitHub 저장소 연결

1. Vercel에 로그인하고 **Add New → Project**를 누릅니다.
2. GitHub의 **showtime3148/123** 저장소를 Import합니다. 목록에 없다면 Vercel의 GitHub 접근 권한에 이 저장소를 추가합니다.
3. Production Branch는 **main**, Root Directory는 저장소 루트로 설정합니다.
4. Framework Preset은 **FastAPI**를 선택합니다. Build Command와 Output Directory는 별도로 덮어쓰지 않습니다.

`vercel.json`과 루트 `main.py`가 포함되어 있습니다. Python 버전은 `.python-version`의 3.12를 사용합니다. OCR 파일도 저장소에 포함되어 있으므로 Tesseract 설치 명령은 필요 없습니다.

## 2. 환경변수 입력

Deploy 전에 **Environment Variables**에 다음 두 개를 입력합니다. 기존 프로젝트라면 **Settings → Environment Variables**에서 입력한 다음 다시 배포합니다.

| 이름 | 값 |
| --- | --- |
| `GCE_ACCESS_PASSWORD` | 선생님들에게 알려줄 접속 비밀번호. 12자 이상 |
| `GCE_OPENAI_API_KEY` | 관리자의 OpenAI API 키. API 결제 및 사용 권한이 있는 키 |

키는 저장소나 채팅에 넣지 말고 Vercel 설정 화면에 직접 입력하세요. 배포 대상인 **Production**에 적용합니다. Preview에서도 테스트할 때는 Preview 환경에도 설정해야 합니다. API 키는 가능하면 Vercel의 민감한 환경변수로 등록합니다.

필요한 경우 다음 항목을 추가할 수 있습니다.

| 이름 | 용도 |
| --- | --- |
| `GCE_CLOSE_AT` | 이용 종료 시각. 실제 사용할 날짜에 맞춰 `YYYY-MM-DDT23:59:00+09:00` 형식으로 입력. 이 예시 문자열 자체를 입력하지 마세요 |
| `GCE_SESSION_SECRET` | 로그인 서명용 임의의 32자 이상 문자열. 생략하면 API 키에서 용도를 분리한 서명 키를 생성 |
| `GCE_MODEL` | 웹 검색을 지원하는 OpenAI 모델. 기본값 `gpt-4.1-mini` |
| `GCE_ALLOWED_HOSTS` | 사용자 지정 도메인이 있으면 도메인만 입력. 여러 개는 쉼표로 구분 |

Vercel의 시스템 환경변수 자동 노출은 기본 설정을 유지하세요. 앱이 `VERCEL`과 Vercel 도메인 변수를 이용해 배포 모드와 허용 도메인을 확인합니다. 이를 꺼둔 프로젝트라면 다시 켜거나 `GCE_HOSTING=vercel`과 `GCE_ALLOWED_HOSTS`를 직접 설정해야 합니다.

## 3. Deploy 후 확인

1. **Deploy**를 누르고 완료되면 Vercel이 발급한 **Production 주소**를 엽니다.
2. 접속 비밀번호로 로그인합니다.
3. 아래 문장을 붙여넣고 문서에서 **Theme**을 찾는지 확인합니다.

   > An educator wants to update the font of their entire Google Site. Which of these features would accomplish this? Preview / Pages / Settings / Theme

4. 문제 화면 이미지를 올려 문자 인식도 확인합니다. 첫 실행은 OCR 파일을 받는 시간이 걸립니다.
5. **웹 출처로 다시 검증**을 눌러 실제 OpenAI 키로 웹 검색과 출처 표시를 확인합니다. 이 단계에는 API 요금이 발생합니다.
6. 선생님들에게 Production 주소와 접속 비밀번호를 전달합니다. API 키를 전달할 필요는 없습니다.

Vercel 계정 로그인을 요구하는 화면이 나오면 앱 비밀번호 화면과 다릅니다. 프로젝트의 **Deployment Protection**에서 Production 주소에 적용된 접근 설정을 확인하세요.

환경변수를 변경한 뒤에는 **Redeploy**해야 적용됩니다. 코드 변경은 GitHub의 `main`에 push하면 연결된 Vercel 프로젝트가 다시 배포합니다.

## 하루 사용 후

`GCE_CLOSE_AT`을 지정하면 해당 시각부터 로그인과 검색이 차단됩니다. 지정하지 않으면 계속 운영됩니다. 종료 후에는 필요에 따라 Vercel 프로젝트를 삭제하거나 API 키를 폐기할 수 있습니다.

이 구성에는 영구 데이터베이스가 없으므로 **전체 사용자의 일일 웹 검색 100회 제한은 적용되지 않습니다.** 서버 인스턴스별 간단한 속도 제한만 있으며 전역 사용량 상한을 보장하지 않습니다. OpenAI 사용량 화면에서 비용을 확인하세요. 예산 알림은 강제 차단 기능과 다를 수 있습니다.

로그인은 최대 12시간 유지됩니다. 로그아웃은 해당 브라우저의 쿠키를 삭제합니다. 별도로 복사된 로그인 토큰까지 즉시 취소하는 기능은 없습니다. 전체 로그인을 무효화하려면 접속 비밀번호를 바꾸고 다시 배포하세요.

## 처리 방식과 검증 범위

- 이미지 문자 인식은 브라우저 안에서 실행됩니다. OCR 엔진과 영어 데이터는 같은 사이트에서 제공하며 외부 CDN을 사용하지 않습니다.
- 서버는 인식된 문제 텍스트로 포함된 문서를 검색합니다. 확실한 일치가 없거나 웹 검증을 선택하면 문제 텍스트와 문서 후보 일부를 OpenAI에 전송합니다.
- 관리자 API 키는 서버에서만 사용합니다. 문제와 이미지를 별도 사용 기록 데이터베이스에 저장하지 않습니다.
- 함수 실행 시간은 120초로 설정했습니다. 호스팅 요금과 한도는 사용 중인 Vercel 플랜을 따릅니다.
- 자동 테스트의 OpenAI 응답은 모의 데이터입니다. 실제 Vercel 배포와 실제 OpenAI 검색은 계정 연결 및 환경변수 입력 후 위 절차로 확인해야 합니다.

`Invalid host header`가 보이면 사용 중인 도메인을 `GCE_ALLOWED_HOSTS`에 추가하고 다시 배포하세요. 앱 시작 오류는 Vercel의 함수 로그에서 환경변수 누락 여부를 확인합니다. OCR을 불러오지 못하면 새로고침하거나 문제 텍스트를 직접 붙여넣어 검색할 수 있습니다.

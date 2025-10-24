# Meeting Transcriber Web Service

실시간 회의 녹음 및 자동 텍스트 변환 웹 서비스입니다. 브라우저의 음성 인식 기능(Web Speech API)을 사용하여 회의 내용을 실시간으로 텍스트로 변환하고, Google Sheets에 자동으로 저장합니다.

## 주요 기능

- **실시간 음성 인식**: 브라우저의 Web Speech API를 활용한 실시간 음성-텍스트 변환
- **WebSocket 기반 통신**: 실시간 양방향 통신으로 안정적인 데이터 전송
- **Google Sheets 연동**: 회의 내용을 자동으로 Google Sheets에 저장
- **다국어 지원**: 한국어, 영어, 일본어, 중국어 지원
- **직관적인 UI**: Vue.js 기반의 깔끔하고 사용하기 쉬운 인터페이스

## 기술 스택

### 백엔드
- **FastAPI**: 고성능 Python 웹 프레임워크
- **WebSocket**: 실시간 양방향 통신
- **Google Cloud Speech-to-Text API**: 음성 인식 (스트리밍 지원)
- **Google Sheets API**: 데이터 저장

### 프론트엔드
- **Vue.js 3**: 프로그레시브 JavaScript 프레임워크
- **Vite**: 빠른 빌드 도구
- **Web Speech API**: 브라우저 내장 음성 인식

## 시스템 아키텍처

```
[브라우저]
   ↓ Web Speech API (음성 인식)
   ↓ WebSocket (텍스트 전송)
[FastAPI 서버]
   ↓ 텍스트 수집 및 병합
   ↓ 회의 종료 시
[Google Sheets]
   ↓ 회의록 저장
```

## 설치 및 실행

### 1. 사전 요구사항

- Python 3.9 이상
- Node.js 18 이상
- Google Cloud 프로젝트 및 서비스 계정
- Google Sheets API 활성화

### 2. 환경 설정

#### Google Cloud 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API 활성화
3. 서비스 계정 생성 및 JSON 키 다운로드
4. 다운로드한 JSON 키를 `app/config/google_sa.json`에 저장
5. Google Sheets 생성 후 서비스 계정에 편집 권한 부여

#### 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```env
GOOGLE_APPLICATION_CREDENTIALS=app/config/google_sa.json
GOOGLE_SHEET_ID=your_google_sheet_id_here
APP_PORT=8000
APP_LOG_LEVEL=info
DEFAULT_SPEAKER=Unknown
```

### 3. 백엔드 설치 및 실행

```bash
# 가상환경 생성 (권장)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

백엔드 서버가 `http://localhost:8000`에서 실행됩니다.

### 4. 프론트엔드 설치 및 실행

```bash
# frontend 디렉토리로 이동
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

프론트엔드가 `http://localhost:5173`에서 실행됩니다.

## 사용 방법

1. **회의 정보 입력**
   - 화자 이름 (필수)
   - 회의 제목 (선택)
   - 언어 선택 (한국어/영어/일본어/중국어)

2. **회의 시작**
   - "회의 시작" 버튼 클릭
   - 브라우저에서 마이크 권한 허용
   - 녹음이 시작되면 자동으로 음성이 텍스트로 변환됩니다

3. **실시간 텍스트 확인**
   - 화면에 실시간으로 인식된 텍스트가 표시됩니다
   - 녹음 시간이 자동으로 카운트됩니다

4. **회의 종료**
   - "회의 종료" 버튼 클릭
   - 전체 회의 내용이 Google Sheets에 자동으로 저장됩니다
   - 저장 완료 후 결과를 확인할 수 있습니다

## API 엔드포인트

### REST API

- `GET /` - 서버 상태 확인
- `GET /api/v1/transcribe/ping` - 라우터 연결 확인
- `POST /api/v1/transcribe/upload` - 오디오 파일 업로드 및 변환
- `GET /api/v1/transcribe/records` - 저장된 모든 레코드 조회
- `POST /api/v1/transcribe/initialize-sheet` - Google Sheets 초기화
- `POST /api/v1/transcribe/clear-sheet` - Google Sheets 클리어

### WebSocket API

- `WS /ws/record` - 실시간 회의 녹음

#### WebSocket 메시지 형식

**클라이언트 → 서버:**
```json
// 녹음 시작
{"type": "start", "language": "ko", "speaker": "홍길동", "meeting_title": "회의 제목"}

// 텍스트 전송
{"type": "transcription", "text": "인식된 텍스트"}

// 녹음 종료
{"type": "end"}
```

**서버 → 클라이언트:**
```json
// 상태 메시지
{"type": "status", "message": "녹음 시작됨", "session_id": "..."}

// 텍스트 수신 확인
{"type": "transcription_received", "text": "인식된 텍스트"}

// 저장 완료
{"type": "completed", "message": "회의가 저장되었습니다", "sheet_row": 123, "transcription": "전체 텍스트"}

// 에러
{"type": "error", "message": "에러 메시지"}
```

## 프로젝트 구조

```
meeting-transcriber/
├── app/                          # 백엔드 (FastAPI)
│   ├── config/
│   │   ├── settings.py          # 환경 설정
│   │   └── google_sa.json       # Google 서비스 계정 키
│   ├── models/
│   │   └── transcribe.py        # 데이터 모델
│   ├── routers/
│   │   ├── transcribe_router.py # REST API 라우터
│   │   └── websocket_router.py  # WebSocket 라우터
│   ├── services/
│   │   ├── transcribe_service.py    # 음성 인식 서비스 (파일 업로드)
│   │   ├── streaming_service.py     # 스트리밍 음성 인식 서비스
│   │   └── sheets_service.py        # Google Sheets 서비스
│   └── main.py                  # FastAPI 앱 진입점
├── frontend/                     # 프론트엔드 (Vue.js)
│   ├── src/
│   │   ├── components/
│   │   │   └── RecordingControl.vue  # 녹음 제어 컴포넌트
│   │   ├── services/
│   │   │   └── websocket.js          # WebSocket 클라이언트
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   └── vite.config.js
├── .env                         # 환경 변수
├── requirements.txt             # Python 의존성
└── README.md
```

## 브라우저 지원

Web Speech API는 다음 브라우저에서 지원됩니다:
- Google Chrome (권장)
- Microsoft Edge
- Safari (일부 제한)

**참고**: Firefox는 Web Speech API를 지원하지 않습니다.

## 문제 해결

### 음성 인식이 작동하지 않는 경우
1. 마이크 권한이 허용되었는지 확인
2. Chrome 브라우저 사용 권장
3. HTTPS 또는 localhost에서만 작동 (보안 정책)

### WebSocket 연결 실패
1. 백엔드 서버가 실행 중인지 확인
2. CORS 설정 확인 (app/main.py)
3. 방화벽 또는 프록시 설정 확인

### Google Sheets 저장 실패
1. 서비스 계정 키 파일 확인
2. Google Sheets에 서비스 계정 권한 부여 확인
3. GOOGLE_SHEET_ID 환경 변수 확인

## 향후 개발 계획

- [ ] 다중 화자 구분 (Speaker Diarization)
- [ ] AI 기반 회의록 자동 요약
- [ ] 회의 참여자 관리 시스템
- [ ] 회의록 검색 기능
- [ ] 오디오 파일 다운로드 기능
- [ ] 실시간 자막 표시 (Google Speech Streaming API 활용)

## 라이선스

MIT License

## 기여

Pull Request는 언제나 환영합니다!

## 문의

이슈가 있으시면 GitHub Issues에 등록해주세요.

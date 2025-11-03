# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 필요한 가이드를 제공합니다.

## 프로젝트 개요

**Google Cloud Speech-to-Text API**를 사용한 실시간 음성 녹취 및 **화자 분리(Speaker Diarization)** 기능을 지원하는 FastAPI 기반 회의 녹취록 서비스입니다. WebSocket을 통해 실시간 오디오 스트리밍을 처리하고, Google Sheets에 자동으로 저장합니다.

### 주요 기능
- ✅ **실시간 WebSocket 스트리밍**: 프론트엔드에서 오디오 청크를 실시간으로 전송
- ✅ **화자 분리 (Speaker Diarization)**: Google Speech API를 통해 자동으로 화자 구분
- ✅ **화자 매핑**: "Speaker 1" → "홍길동" 등 실명으로 매핑 가능
- ✅ **템플릿 기반 시트 생성**: 회의 시작 시 템플릿 워크시트 탭 자동 복사
- ✅ **실시간 Sheets 기록**: 음성 인식 결과를 즉시 Google Sheets에 저장
- ✅ **파일 업로드 녹취**: WebSocket 외에도 오디오 파일 업로드 방식 지원

## 환경 설정

1. Python 가상환경 생성 및 활성화:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Unix/macOS
source .venv/bin/activate
```

2. 의존성 패키지 설치:
```bash
pip install -r requirements.txt
```

3. `.env` 파일에서 환경 변수 설정:
   - `GOOGLE_APPLICATION_CREDENTIALS`: Google 서비스 계정 JSON 파일 경로 (일반적으로 `app/config/google_sa.json`)
   - `GOOGLE_SHEET_ID`: 녹취록을 저장할 Google Sheets ID (기본 시트)
   - `GOOGLE_TEMPLATE_SHEET_ID`: 템플릿 시트 ID (탭 복사용)
   - `GOOGLE_DRIVE_FOLDER_ID`: Google Drive 폴더 ID (선택)
   - `APP_PORT`: 서버 포트 (기본값: 8000)
   - `APP_LOG_LEVEL`: 로깅 레벨 (기본값: info)
   - `DEFAULT_SPEAKER`: 녹취록의 기본 화자 이름 (기본값: Unknown)
   - `SPEECH_LANGUAGE`: 음성 인식 언어 (기본값: ko-KR)
   - `SPEECH_ENCODING`: 오디오 인코딩 형식 (기본값: WEBM_OPUS)
   - `SPEECH_SAMPLE_RATE`: 샘플링 레이트 (기본값: 48000)
   - `ENABLE_SPEAKER_DIARIZATION`: 화자 분리 활성화 (기본값: True)

## 개발 명령어

### 개발 서버 실행:
```bash
uvicorn app.main:app --reload --port 8000
```

### 서버 테스트:
```bash
# 루트 엔드포인트 확인
curl http://localhost:8000/

# 녹취 라우터 확인
curl http://localhost:8000/api/v1/transcribe/ping

# WebSocket 활성 세션 확인
curl http://localhost:8000/ws/sessions
```

## 아키텍처

### 프로젝트 구조
```
app/
├── config/          # 설정 관리
│   └── settings.py  # .env와 통합된 Pydantic 설정
├── models/          # 데이터 모델
│   └── transcribe.py  # 녹취 관련 Pydantic 모델
├── routers/         # API 라우트 핸들러
│   ├── transcribe_router.py  # 파일 업로드 녹취 엔드포인트 (prefix: /api/v1/transcribe)
│   └── websocket_router.py   # WebSocket 실시간 녹취 엔드포인트 (prefix: /ws)
├── services/        # 비즈니스 로직 계층
│   ├── speech_service.py     # Google Speech-to-Text API 서비스 (화자 분리)
│   ├── streaming_service.py  # 스트리밍 관련 서비스 (레거시)
│   ├── transcribe_service.py # 파일 업로드 녹취 서비스
│   ├── sheets_service.py     # Google Sheets API 서비스
│   └── drive_service.py      # Google Drive API 서비스
└── main.py          # FastAPI 애플리케이션 진입점
```

### 실시간 녹취 데이터 흐름

```
프론트엔드 (WebSocket 클라이언트)
  ↓ {"type": "start", "language": "ko-KR", "participants": "홍길동,김철수"}
  ↓ {"type": "audio", "data": "base64_encoded_audio_chunk"}
websocket_router.py (/ws/record)
  ↓ Base64 디코딩 → audio_bytes
  ↓ session["speech_session"].send_audio(audio_bytes)
speech_service.py (SpeechStreamingSession)
  ↓ audio_queue.put() → request_generator()
  ↓ Speech API 실시간 스트리밍 (WEBM_OPUS, 화자 분리 활성화)
Google Cloud Speech-to-Text API (v1p1beta1)
  ↓ streaming_recognize() 응답 (화자 태그 포함)
  ↓ _process_responses() 실시간 수신
  ↓ result_callback({"text": "...", "speaker_id": 1})
websocket_router.py (on_speech_result)
  ↓ 화자 매핑 확인 (Speaker 1 → 홍길동)
  ↓ sheets_service.append_transcription_with_speaker()
Google Sheets API
  ✅ 실시간 기록 완료 (화자 변경 시 [화자명] 포맷)
```

### 설정 시스템
- 타입 안전한 설정을 위해 `pydantic-settings` 사용
- 프로젝트 루트의 `.env` 파일에서 설정 로드
- 설정 인스턴스는 `from app.config.settings import settings`로 가져오기
- 모든 설정은 환경 변수 이름과 일치하는 Field alias 사용

### API 엔드포인트

#### 1. WebSocket 실시간 녹취
- **엔드포인트**: `ws://localhost:8000/ws/record`
- **프로토콜**: WebSocket
- **메시지 형식**:
  - 클라이언트 → 서버:
    - `{"type": "start", "language": "ko-KR", "speaker": "홍길동", "meeting_title": "주간 회의", "participants": "홍길동,김철수"}`
    - `{"type": "audio", "data": "<base64>"}`
    - `{"type": "speaker_mapping", "speaker_id": 1, "speaker_name": "홍길동"}`
    - `{"type": "end"}`
  - 서버 → 클라이언트:
    - `{"type": "status", "message": "녹음 시작됨", "session_id": "...", "sheet_link": "..."}`
    - `{"type": "transcription_recorded", "text": "...", "speaker": "홍길동", "speaker_changed": true}`
    - `{"type": "speaker_mapping_required", "speaker_id": 1, "available_names": [...]}`
    - `{"type": "completed", "message": "...", "sheet_link": "..."}`

#### 2. 파일 업로드 녹취
- **엔드포인트**: `POST /api/v1/transcribe/upload`
- **파라미터**:
  - `audio_file`: 오디오 파일 (mp3, wav, m4a 등)
  - `speaker`: 화자 이름 (선택)
  - `language`: 언어 코드 (기본값: ko)
  - `meeting_title`: 회의 제목 (선택)

#### 3. 기타 엔드포인트
- `GET /api/v1/transcribe/records`: 저장된 레코드 조회
- `POST /api/v1/transcribe/initialize-sheet`: 시트 초기화
- `GET /ws/sessions`: 활성 WebSocket 세션 목록

### 주요 의존성
- **FastAPI**: 웹 프레임워크
- **Uvicorn**: ASGI 서버
- **Google Cloud Speech-to-Text (v1p1beta1)**: 음성 인식 및 화자 분리
- **Google Sheets API (v4)**: 녹취록 저장
- **Google Drive API (v3)**: 파일 관리
- **Pydantic**: 데이터 검증 및 설정 관리

## 개발 가이드

### 코딩 규칙
- 프로젝트 코드와 주석은 **한국어** 사용
- 비즈니스 로직은 `services/` 디렉토리에 구현
- API 요청/응답 모델은 `models/` 디렉토리에 Pydantic 모델로 정의
- 민감한 정보(서비스 계정 JSON, .env)는 git 추적 제외

### 주요 서비스 클래스
- **`SpeechService`** (`speech_service.py`): Google Speech API 클라이언트, 화자 분리 설정
- **`SpeechStreamingSession`** (`speech_service.py`): 지속적인 Speech API 스트리밍 세션 관리
- **`GoogleSheetsService`** (`sheets_service.py`):
  - 템플릿 탭 복사 (`create_meeting_sheet`)
  - 화자 정보와 함께 녹취 기록 (`append_transcription_with_speaker`)
  - 화자 레이블 일괄 업데이트 (`update_speaker_labels`)

### 화자 분리 작동 방식
1. Speech API에 `enable_speaker_diarization=True` 설정
2. API 응답에서 `alternative.words[0].speaker_tag` 추출 (1, 2, 3...)
3. 클라이언트가 참석자 명단 제공 (`participants: "홍길동,김철수"`)
4. 첫 발화 시 서버가 클라이언트에 `speaker_mapping_required` 메시지 전송
5. 클라이언트가 매핑 정보 전송 (`speaker_id: 1, speaker_name: "홍길동"`)
6. 이후 자동으로 매핑된 이름으로 기록

### Google Sheets 포맷
- 템플릿 시트에서 탭 복사하여 각 회의별 독립 탭 생성
- **B2**: 회의 안건
- **D3**: 날짜/시간
- **C13~**: 녹취 내용 (화자 변경 시 `[화자명] 텍스트` 형식)

### 트러블슈팅
- **WebSocket 연결 안 됨**: CORS 설정 확인 (`main.py:9-15`)
- **Speech API 타임아웃**: 첫 오디오 청크가 도착한 후 스트림 시작 (`websocket_router.py:236-247`)
- **화자 분리 안 됨**: `enable_speaker_diarization=True` 확인 (`settings.py:38-42`)

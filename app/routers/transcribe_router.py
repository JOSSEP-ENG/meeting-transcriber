from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config.settings import settings
from app.models.transcribe import SheetRecord, TranscribeResponse
from app.services.sheets_service import sheets_service
from app.services.transcribe_service import transcribe_service

router = APIRouter(prefix="/api/v1/transcribe", tags=["Transcribe"])


@router.get("/ping")
def ping():
    return {"message": "Transcribe router is connected successfully"}


@router.post("/upload", response_model=TranscribeResponse)
async def upload_and_transcribe(
    audio_file: UploadFile = File(..., description="업로드할 오디오 파일"),
    speaker: str = Form(None, description="화자 이름 (선택)"),
    language: str = Form("ko", description="음성 언어 코드 (기본값: ko)"),
    meeting_title: str = Form(None, description="회의 제목 (선택)"),
):
    """
    음성 파일을 업로드하여 텍스트로 변환하고 Google Sheets에 저장

    Args:
        audio_file: 오디오 파일 (mp3, wav, m4a 등)
        speaker: 화자 이름 (미지정시 DEFAULT_SPEAKER 사용)
        language: 음성 언어 코드 (예: ko, en, ja)
        meeting_title: 회의 제목

    Returns:
        TranscribeResponse: 녹취 결과
    """
    try:
        # 1. 오디오 파일 유효성 검사 (파일 확장자로 확인)
        allowed_extensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".mp4"]
        file_ext = audio_file.filename.lower()[-4:] if audio_file.filename else ""

        is_audio = audio_file.content_type and audio_file.content_type.startswith("audio/")
        is_allowed_ext = any(file_ext.endswith(ext) for ext in allowed_extensions)

        if not (is_audio or is_allowed_ext):
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 파일 형식입니다: {audio_file.filename}",
            )

        # 2. 음성 인식 (Whisper API)
        transcription = await transcribe_service.transcribe_audio(
            audio_file.file, language=language
        )

        # 3. 화자 이름 설정
        speaker_name = speaker or settings.default_speaker

        # 4. 현재 시각
        now = datetime.now()

        # 5. Google Sheets에 저장
        sheet_record = SheetRecord(
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
            speaker=speaker_name,
            transcription=transcription,
            meeting_title=meeting_title,
        )

        row_number = await sheets_service.append_record(sheet_record)

        # 6. 응답 반환
        return TranscribeResponse(
            success=True,
            transcription=transcription,
            speaker=speaker_name,
            timestamp=now,
            sheet_row=row_number,
            message="녹취가 성공적으로 완료되었습니다.",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"녹취 처리 실패: {str(e)}")


@router.get("/records")
async def get_all_records():
    """
    Google Sheets에 저장된 모든 녹취 레코드 조회

    Returns:
        저장된 모든 레코드
    """
    try:
        records = await sheets_service.get_all_records()
        return {"success": True, "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"레코드 조회 실패: {str(e)}")


@router.post("/initialize-sheet")
async def initialize_sheet():
    """
    Google Sheets 초기화 (헤더 생성)

    Returns:
        초기화 결과
    """
    try:
        await sheets_service.initialize_sheet()
        return {"success": True, "message": "시트가 초기화되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시트 초기화 실패: {str(e)}")

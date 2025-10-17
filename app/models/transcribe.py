from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    """음성 녹취 요청 모델"""

    speaker: Optional[str] = Field(
        default=None, description="화자 이름 (미지정시 DEFAULT_SPEAKER 사용)"
    )
    language: Optional[str] = Field(
        default="ko", description="음성 언어 코드 (예: ko, en, ja)"
    )
    meeting_title: Optional[str] = Field(
        default=None, description="회의 제목 (미지정시 자동 생성)"
    )


class TranscribeResponse(BaseModel):
    """음성 녹취 응답 모델"""

    success: bool = Field(description="녹취 성공 여부")
    transcription: str = Field(description="변환된 텍스트")
    speaker: str = Field(description="화자 이름")
    timestamp: datetime = Field(description="녹취 시각")
    sheet_row: Optional[int] = Field(default=None, description="Google Sheets 행 번호")
    message: Optional[str] = Field(default=None, description="추가 메시지")


class SheetRecord(BaseModel):
    """Google Sheets에 저장할 레코드 모델"""

    timestamp: str = Field(description="녹취 시각 (YYYY-MM-DD HH:MM:SS)")
    speaker: str = Field(description="화자 이름")
    transcription: str = Field(description="변환된 텍스트")
    meeting_title: Optional[str] = Field(default=None, description="회의 제목")

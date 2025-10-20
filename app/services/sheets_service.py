from datetime import datetime
from typing import List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config.settings import settings
from app.models.transcribe import SheetRecord


class GoogleSheetsService:
    """Google Sheets API 연동 서비스"""

    def __init__(self):
        # Google Sheets API 스코프
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        self.service = None
        self.sheet_id = settings.google_sheet_id

    def _get_service(self):
        """서비스 클라이언트를 lazy initialization으로 생성"""
        if self.service is None:
            # 서비스 계정 인증
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials, scopes=self.scopes
            )
            # Sheets API 클라이언트 생성
            self.service = build("sheets", "v4", credentials=credentials)
        return self.service

    async def initialize_sheet(self) -> None:
        """
        시트 초기화 (헤더 행 생성)
        이미 헤더가 있으면 스킵
        """
        try:
            service = self._get_service()
            # 첫 번째 행 읽기
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=self.sheet_id, range="A1:D1")
                .execute()
            )

            values = result.get("values", [])

            # 헤더가 없으면 생성
            if not values:
                headers = [["시각", "화자", "녹취 내용", "회의 제목"]]
                service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range="A1:D1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

        except Exception as e:
            raise Exception(f"시트 초기화 실패: {str(e)}")

    async def append_record(self, record: SheetRecord) -> int:
        """
        녹취 레코드를 시트에 추가

        Args:
            record: 추가할 레코드

        Returns:
            추가된 행 번호

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()
            # 레코드를 리스트로 변환
            row_data = [
                [
                    record.timestamp,
                    record.speaker,
                    record.transcription,
                    record.meeting_title or "",
                ]
            ]

            # 시트에 추가
            result = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.sheet_id,
                    range="A:D",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": row_data},
                )
                .execute()
            )

            # 추가된 행 번호 추출
            updated_range = result.get("updates", {}).get("updatedRange", "")
            # 예: 'Sheet1!A2:D2' -> 2
            row_number = int(updated_range.split("!")[1].split(":")[0][1:])

            return row_number

        except Exception as e:
            raise Exception(f"시트 레코드 추가 실패: {str(e)}")

    async def get_all_records(self) -> List[List[str]]:
        """
        시트의 모든 레코드 조회 (헤더 제외)

        Returns:
            레코드 리스트

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=self.sheet_id, range="A2:D")
                .execute()
            )

            values = result.get("values", [])
            return values

        except Exception as e:
            raise Exception(f"시트 레코드 조회 실패: {str(e)}")

    async def get_headers(self) -> List[str]:
        """
        시트의 헤더 행 조회 (디버깅용)

        Returns:
            헤더 리스트

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=self.sheet_id, range="A1:Z1")
                .execute()
            )

            values = result.get("values", [[]])[0]
            return values

        except Exception as e:
            raise Exception(f"시트 헤더 조회 실패: {str(e)}")

    async def clear_and_reinitialize(self) -> None:
        """
        시트를 완전히 클리어하고 헤더를 다시 생성

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()

            # 시트 전체 클리어
            service.spreadsheets().values().clear(
                spreadsheetId=self.sheet_id,
                range="A:Z"
            ).execute()

            # 헤더 생성
            headers = [["시각", "화자", "녹취 내용", "회의 제목"]]
            service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range="A1:D1",
                valueInputOption="RAW",
                body={"values": headers},
            ).execute()

        except Exception as e:
            raise Exception(f"시트 클리어 및 초기화 실패: {str(e)}")


# 싱글톤 인스턴스
sheets_service = GoogleSheetsService()

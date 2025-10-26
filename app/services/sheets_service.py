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

    async def create_meeting_sheet(
        self,
        meeting_title: str,
        meeting_date: Optional[str] = None,
        meeting_time: Optional[str] = None,
        location: Optional[str] = None
    ) -> dict:
        """
        템플릿 워크시트 탭을 복사하여 새 회의록 탭 생성

        Args:
            meeting_title: 회의 제목
            meeting_date: 회의 날짜 (YYYY-MM-DD 형식)
            meeting_time: 회의 시간 (예: "9:00-10:00")
            location: 회의 장소

        Returns:
            생성된 탭 정보 (file_id, tab_id, tab_name, web_link)

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()
            template_sheet_id = settings.google_template_sheet_id

            # 1. 템플릿 시트의 첫 번째 워크시트(탭) ID 가져오기
            sheet_metadata = service.spreadsheets().get(
                spreadsheetId=template_sheet_id
            ).execute()

            sheets = sheet_metadata.get('sheets', [])
            if not sheets:
                raise Exception("템플릿 시트에 워크시트가 없습니다")

            # 첫 번째 탭을 템플릿으로 사용
            template_tab_id = sheets[0]['properties']['sheetId']
            template_tab_name = sheets[0]['properties']['title']

            print(f"DEBUG: Template tab ID: {template_tab_id}, Name: {template_tab_name}")

            # 2. 새 탭 이름 생성
            if not meeting_date:
                meeting_date = datetime.now().strftime("%Y-%m-%d")

            new_tab_name = f"{meeting_date} {meeting_title}"

            # 3. 템플릿 탭 복사
            copy_request = {
                "duplicateSheet": {
                    "sourceSheetId": template_tab_id,
                    "newSheetName": new_tab_name
                }
            }

            response = service.spreadsheets().batchUpdate(
                spreadsheetId=template_sheet_id,
                body={"requests": [copy_request]}
            ).execute()

            # 복사된 탭 ID 가져오기
            new_tab_id = response['replies'][0]['duplicateSheet']['properties']['sheetId']

            print(f"SUCCESS: Tab copied - ID: {new_tab_id}, Name: {new_tab_name}")

            # 4. 회의 메타 정보 입력 (행2, 행3)
            # 날짜/시간 포맷팅
            formatted_date = meeting_date.replace("-", ".")
            if meeting_time:
                datetime_info = f"{formatted_date} / {meeting_time}"
            else:
                datetime_info = formatted_date

            # 배치 업데이트
            updates = [
                {
                    "range": f"'{new_tab_name}'!B2:C2",  # 회의 안건
                    "values": [["회의 안건", meeting_title]]
                },
                {
                    "range": f"'{new_tab_name}'!D3",  # 날짜/시간
                    "values": [[datetime_info]]
                }
            ]

            # 장소 정보 (있는 경우)
            if location:
                updates.append({
                    "range": f"'{new_tab_name}'!D4",
                    "values": [[location]]
                })

            service.spreadsheets().values().batchUpdate(
                spreadsheetId=template_sheet_id,
                body={"data": updates, "valueInputOption": "RAW"}
            ).execute()

            print(f"SUCCESS: Metadata updated for tab: {new_tab_name}")

            # 5. 웹 링크 생성 (특정 탭으로 이동)
            web_link = f"https://docs.google.com/spreadsheets/d/{template_sheet_id}/edit#gid={new_tab_id}"

            return {
                "file_id": template_sheet_id,  # 같은 파일
                "tab_id": new_tab_id,  # 새 탭 ID
                "tab_name": new_tab_name,  # 탭 이름
                "web_link": web_link,
                "created_time": datetime.now().isoformat()
            }

        except Exception as e:
            import traceback
            print(f"ERROR: {str(e)}")
            print(f"TRACEBACK: {traceback.format_exc()}")
            raise Exception(f"회의록 탭 생성 실패: {str(e)}")

    async def append_transcription_to_sheet(
        self,
        sheet_id: str,
        tab_name: str,
        transcription: str,
        start_row: int = 13  # C13부터 시작
    ) -> int:
        """
        특정 탭의 C열에 녹취 내용 추가

        Args:
            sheet_id: Google Sheets 파일 ID
            tab_name: 워크시트 탭 이름
            transcription: 녹취 텍스트
            start_row: 시작 행 번호 (기본값: 13)

        Returns:
            추가된 행 번호

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()

            # 현재 C열의 마지막 데이터 행 찾기
            # C13부터 C1000까지 읽어서 마지막 비어있지 않은 행 찾기
            range_to_read = f"'{tab_name}'!C{start_row}:C1000"
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_to_read
            ).execute()

            values = result.get("values", [])

            # 다음 빈 행 계산
            if values:
                # 마지막 데이터가 있는 행의 다음 행
                next_row = start_row + len(values)
            else:
                # 데이터가 없으면 start_row부터 시작
                next_row = start_row

            # C열에 녹취 내용 추가
            range_to_update = f"'{tab_name}'!C{next_row}"
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_to_update,
                valueInputOption="RAW",
                body={"values": [[transcription]]}
            ).execute()

            print(f"SUCCESS: Transcription added to {range_to_update}")
            return next_row

        except Exception as e:
            raise Exception(f"녹취 내용 추가 실패: {str(e)}")


# 싱글톤 인스턴스
sheets_service = GoogleSheetsService()

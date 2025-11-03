from datetime import datetime
from typing import List, Optional
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config.settings import settings
from app.models.transcribe import SheetRecord

logger = logging.getLogger(__name__)


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
            import sys
            service = self._get_service()
            # 템플릿 시트에서 탭 복사
            template_sheet_id = settings.google_template_sheet_id
            print(f"[SHEET] Using template sheet ID: {template_sheet_id}", file=sys.stderr, flush=True)

            # 1. 시트의 모든 탭 정보 가져오기
            print(f"[SHEET] Fetching sheet metadata...", file=sys.stderr, flush=True)
            sheet_metadata = service.spreadsheets().get(
                spreadsheetId=template_sheet_id
            ).execute()
            print(f"[SHEET] Sheet metadata fetched successfully", file=sys.stderr, flush=True)

            sheets = sheet_metadata.get('sheets', [])
            if not sheets:
                raise Exception("템플릿 시트에 워크시트가 없습니다")

            # "템플릿" 또는 "Template" 이름을 가진 탭 찾기
            # 없으면 첫 번째 탭을 템플릿으로 사용
            template_tab_id = None
            template_tab_name = None

            for sheet in sheets:
                sheet_title = sheet['properties']['title']
                if sheet_title in ['템플릿', 'Template', 'TEMPLATE', 'template']:
                    template_tab_id = sheet['properties']['sheetId']
                    template_tab_name = sheet_title
                    print(f"[OK] Template tab found: {template_tab_name} (ID: {template_tab_id})")
                    break

            # 템플릿 탭을 못 찾으면 첫 번째 탭 사용
            if template_tab_id is None:
                template_tab_id = sheets[0]['properties']['sheetId']
                template_tab_name = sheets[0]['properties']['title']
                print(f"[WARNING] Template tab not found, using first tab: {template_tab_name} (ID: {template_tab_id})")

            print(f"[SHEET] Template tab ID: {template_tab_id}, Name: {template_tab_name}", file=sys.stderr, flush=True)

            # 2. 새 탭 이름 생성 (중복 방지를 위해 타임스탬프 추가)
            print(f"[SHEET] Creating new tab name...", file=sys.stderr, flush=True)
            if not meeting_date:
                meeting_date = datetime.now().strftime("%Y-%m-%d")

            # 마이크로초까지 포함한 타임스탬프로 중복 방지
            timestamp = datetime.now().strftime("%H%M%S-%f")[:15]  # HHMMSS-mmmmmm 형식
            new_tab_name = f"{meeting_date} {meeting_title} ({timestamp})"

            # 3. 템플릿 탭 복사
            print(f"[SHEET] Copying template tab '{template_tab_name}' to '{new_tab_name}'...", file=sys.stderr, flush=True)
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

            print(f"[SUCCESS] Tab copied - ID: {new_tab_id}, Name: {new_tab_name}", file=sys.stderr, flush=True)

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

            print(f"[SUCCESS] Metadata updated for tab: {new_tab_name}", file=sys.stderr, flush=True)

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

    async def append_transcription_with_speaker(
        self,
        sheet_id: str,
        tab_name: str,
        text: str,
        current_speaker: str,
        last_speaker: Optional[str],
        start_row: int = 13
    ) -> dict:
        """
        화자 정보와 함께 녹취 내용 기록

        포맷 규칙:
        1. 화자가 바뀌면: 빈 줄 + [화자명] 텍스트
        2. 같은 화자: 텍스트만 (화자명 생략)

        Args:
            sheet_id: Google Sheets 파일 ID
            tab_name: 워크시트 탭 이름
            text: 녹취 텍스트
            current_speaker: 현재 화자 ("홍길동" 또는 "Speaker 1")
            last_speaker: 이전 화자 (None이면 첫 발화)
            start_row: 시작 행 번호 (기본값: 13)

        Returns:
            {
                "row": 기록된 행 번호,
                "speaker": 화자명,
                "speaker_changed": 화자 변경 여부,
                "formatted_text": 실제 기록된 텍스트
            }
        """
        try:
            service = self._get_service()

            # 1. 현재 마지막 행 찾기
            range_to_read = f"'{tab_name}'!C{start_row}:C1000"
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_to_read
            ).execute()

            values = result.get("values", [])
            current_row = start_row + len(values)

            # 2. 화자 변경 감지
            speaker_changed = (last_speaker != current_speaker)

            # 3. 기록할 데이터 준비
            rows_to_append = []

            # 화자가 바뀌고 첫 발화가 아니면 빈 줄 추가
            if speaker_changed and last_speaker is not None:
                rows_to_append.append([""])

            # 텍스트 포맷팅
            if speaker_changed:
                formatted_text = f"[{current_speaker}] {text}"
            else:
                formatted_text = text

            rows_to_append.append([formatted_text])

            # 4. 시트에 기록
            start_write_row = current_row
            end_write_row = current_row + len(rows_to_append) - 1

            range_to_update = f"'{tab_name}'!C{start_write_row}:C{end_write_row}"

            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_to_update,
                valueInputOption="RAW",
                body={"values": rows_to_append}
            ).execute()

            logger.info(
                f"녹취 기록 완료 - 화자: {current_speaker}, "
                f"행: {start_write_row}, 변경: {speaker_changed}"
            )

            return {
                "row": start_write_row,
                "speaker": current_speaker,
                "speaker_changed": speaker_changed,
                "formatted_text": formatted_text
            }

        except Exception as e:
            logger.error(f"녹취 기록 실패: {e}")
            raise Exception(f"녹취 기록 실패: {str(e)}")

    async def update_speaker_labels(
        self,
        sheet_id: str,
        tab_name: str,
        old_label: str,
        new_label: str,
        start_row: int = 13
    ) -> int:
        """
        화자 레이블 일괄 업데이트

        예: "[Speaker 1]" → "[홍길동]"

        Args:
            sheet_id: Google Sheets 파일 ID
            tab_name: 워크시트 탭 이름
            old_label: 기존 레이블 ("Speaker 1")
            new_label: 새 레이블 ("홍길동")
            start_row: 시작 행 번호 (기본값: 13)

        Returns:
            업데이트된 행 개수
        """
        try:
            service = self._get_service()

            # 1. 전체 데이터 읽기
            range_to_read = f"'{tab_name}'!C{start_row}:C1000"
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_to_read
            ).execute()

            values = result.get("values", [])
            if not values:
                return 0

            # 2. 레이블 찾아서 변경
            updated_count = 0
            updated_values = []

            old_prefix = f"[{old_label}]"
            new_prefix = f"[{new_label}]"

            for row in values:
                if not row:
                    updated_values.append(row)
                    continue

                cell_value = row[0]

                # "[Speaker 1] 텍스트" → "[홍길동] 텍스트"
                if cell_value.startswith(old_prefix):
                    new_value = cell_value.replace(old_prefix, new_prefix, 1)
                    updated_values.append([new_value])
                    updated_count += 1
                else:
                    updated_values.append(row)

            # 3. 업데이트
            if updated_count > 0:
                range_to_update = f"'{tab_name}'!C{start_row}:C{start_row + len(updated_values) - 1}"

                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=range_to_update,
                    valueInputOption="RAW",
                    body={"values": updated_values}
                ).execute()

                logger.info(f"화자 레이블 업데이트 완료: {updated_count}개 행")

            return updated_count

        except Exception as e:
            logger.error(f"레이블 업데이트 실패: {e}")
            return 0


# 싱글톤 인스턴스
sheets_service = GoogleSheetsService()

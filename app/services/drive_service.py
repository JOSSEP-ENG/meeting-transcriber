from datetime import datetime
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.config.settings import settings


class GoogleDriveService:
    """Google Drive API 연동 서비스"""

    def __init__(self):
        # Google Drive API 스코프
        self.scopes = [
            "https://www.googleapis.com/auth/drive",  # 모든 Drive 파일 접근 (템플릿 복사용)
            "https://www.googleapis.com/auth/spreadsheets",  # Sheets 접근
        ]
        self.service = None

    def _get_service(self):
        """서비스 클라이언트를 lazy initialization으로 생성"""
        if self.service is None:
            # 서비스 계정 인증
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials, scopes=self.scopes
            )
            # Drive API 클라이언트 생성
            self.service = build("drive", "v3", credentials=credentials)
        return self.service

    async def copy_template_sheet(
        self,
        meeting_title: str,
        meeting_date: Optional[str] = None,
        folder_id: Optional[str] = None
    ) -> dict:
        """
        템플릿 시트를 복사하여 새 회의록 파일 생성

        Args:
            meeting_title: 회의 제목
            meeting_date: 회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)
            folder_id: 파일을 저장할 폴더 ID (없으면 루트에 생성)

        Returns:
            생성된 파일 정보 (id, name, webViewLink 등)

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()

            # 날짜 설정
            if not meeting_date:
                meeting_date = datetime.now().strftime("%Y-%m-%d")

            # 새 파일명 생성: "날짜 회의제목"
            new_file_name = f"{meeting_date} {meeting_title}"

            # 복사 요청 body
            copy_body = {
                "name": new_file_name,
            }

            # 폴더 지정 (설정된 경우)
            if folder_id or settings.google_drive_folder_id:
                target_folder = folder_id or settings.google_drive_folder_id
                copy_body["parents"] = [target_folder]

            # 템플릿 시트 복사
            print(f"INFO: Copying template sheet: {settings.google_template_sheet_id}")
            print(f"INFO: New file name: {new_file_name}")

            copied_file = (
                service.files()
                .copy(fileId=settings.google_template_sheet_id, body=copy_body)
                .execute()
            )

            # 파일 정보 조회 (webViewLink 포함)
            file_info = (
                service.files()
                .get(fileId=copied_file["id"], fields="id,name,webViewLink,createdTime")
                .execute()
            )

            print(f"INFO: New file created: {file_info['id']}")
            print(f"INFO: Web link: {file_info.get('webViewLink', 'N/A')}")

            return file_info

        except Exception as e:
            raise Exception(f"템플릿 시트 복사 실패: {str(e)}")

    async def get_file_info(self, file_id: str) -> dict:
        """
        파일 정보 조회

        Args:
            file_id: Google Drive 파일 ID

        Returns:
            파일 정보

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()
            file_info = (
                service.files()
                .get(fileId=file_id, fields="id,name,webViewLink,createdTime,modifiedTime")
                .execute()
            )
            return file_info

        except Exception as e:
            raise Exception(f"파일 정보 조회 실패: {str(e)}")

    async def delete_file(self, file_id: str) -> bool:
        """
        파일 삭제

        Args:
            file_id: Google Drive 파일 ID

        Returns:
            삭제 성공 여부

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            service = self._get_service()
            service.files().delete(fileId=file_id).execute()
            print(f"INFO: File deleted: {file_id}")
            return True

        except Exception as e:
            raise Exception(f"파일 삭제 실패: {str(e)}")


# 싱글톤 인스턴스
drive_service = GoogleDriveService()

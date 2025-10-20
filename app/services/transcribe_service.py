from typing import BinaryIO, Optional

from google.cloud import speech
from google.oauth2 import service_account

from app.config.settings import settings


class TranscribeService:
    """Google Cloud Speech-to-Text API를 사용한 음성 인식 서비스"""

    def __init__(self):
        self.client = None

    def _get_client(self):
        """Google Speech 클라이언트를 lazy initialization으로 생성"""
        if self.client is None:
            # Google 서비스 계정 인증
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials
            )
            self.client = speech.SpeechClient(credentials=credentials)
        return self.client

    async def transcribe_audio(
        self, audio_file: BinaryIO, language: Optional[str] = "ko"
    ) -> str:
        """
        음성 파일을 텍스트로 변환

        Args:
            audio_file: 업로드된 오디오 파일 객체
            language: 음성 언어 코드 (기본값: ko, 영어는 en-US)

        Returns:
            변환된 텍스트

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            client = self._get_client()

            # 오디오 파일 읽기
            content = audio_file.read()

            # Google Speech-to-Text 설정
            audio = speech.RecognitionAudio(content=content)

            # 언어 코드 매핑 (ko -> ko-KR, en -> en-US)
            language_code_map = {
                "ko": "ko-KR",
                "en": "en-US",
                "ja": "ja-JP",
                "zh": "zh-CN",
            }
            language_code = language_code_map.get(language, f"{language}-KR")

            # 오디오 인코딩 설정
            # MP3 파일은 LINEAR16 인코딩으로 처리하거나 sample_rate 지정 필요
            # 짧은 오디오의 경우 recognize 메서드 사용
            # 긴 오디오의 경우 long_running_recognize 사용 고려
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                # sample_rate_hertz=16000,  # MP3는 자동 감지됨
                language_code=language_code,
                enable_automatic_punctuation=True,  # 자동 문장 부호
                model="default",  # 기본 모델
                # audio_channel_count=1,  # 모노 채널
            )

            # 음성 인식 수행
            response = client.recognize(config=config, audio=audio)

            # 디버깅: 응답 확인
            print(f"DEBUG: Speech API response received")
            print(f"DEBUG: Number of results: {len(response.results)}")

            # 결과 추출
            if not response.results:
                print("DEBUG: No results from Speech API")
                return ""

            # 모든 결과를 합쳐서 반환
            transcript = " ".join(
                [result.alternatives[0].transcript for result in response.results]
            )

            print(f"DEBUG: Transcription: {transcript}")
            return transcript

        except Exception as e:
            print(f"DEBUG: Exception occurred: {str(e)}")
            raise Exception(f"음성 인식 실패: {str(e)}")


# 싱글톤 인스턴스
transcribe_service = TranscribeService()

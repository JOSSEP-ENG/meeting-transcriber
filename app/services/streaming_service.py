import asyncio
from typing import AsyncGenerator, Optional

from google.cloud import speech
from google.oauth2 import service_account

from app.config.settings import settings


class StreamingTranscribeService:
    """Google Cloud Speech-to-Text Streaming API를 사용한 실시간 음성 인식 서비스"""

    def __init__(self):
        self.client = None

    def _get_client(self):
        """Google Speech 클라이언트를 lazy initialization으로 생성"""
        if self.client is None:
            credentials = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials
            )
            self.client = speech.SpeechClient(credentials=credentials)
        return self.client

    async def transcribe_stream(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        language: str = "ko",
    ) -> AsyncGenerator[str, None]:
        """
        오디오 스트림을 실시간으로 텍스트로 변환

        Args:
            audio_generator: 오디오 청크를 생성하는 비동기 제너레이터
            language: 음성 언어 코드 (기본값: ko)

        Yields:
            실시간으로 변환된 텍스트 청크
        """
        client = self._get_client()

        # 언어 코드 매핑
        language_code_map = {
            "ko": "ko-KR",
            "en": "en-US",
            "ja": "ja-JP",
            "zh": "zh-CN",
        }
        language_code = language_code_map.get(language, f"{language}-KR")

        # 스트리밍 설정
        config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language_code,
                enable_automatic_punctuation=True,
                model="default",
            ),
            interim_results=False,  # 중간 결과는 사용하지 않음 (종료 후 처리)
        )

        # 동기 제너레이터를 비동기로 래핑
        def sync_audio_generator():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async_gen = audio_generator.__aiter__()
                while True:
                    try:
                        chunk = loop.run_until_complete(async_gen.__anext__())
                        yield speech.StreamingRecognizeRequest(audio_content=chunk)
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()

        # 스트리밍 인식 수행
        requests = sync_audio_generator()
        responses = client.streaming_recognize(config, requests)

        # 결과 처리
        for response in responses:
            for result in response.results:
                if result.is_final:
                    transcript = result.alternatives[0].transcript
                    print(f"DEBUG: Streaming transcription: {transcript}")
                    yield transcript


# 싱글톤 인스턴스
streaming_service = StreamingTranscribeService()

import io
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional

import librosa
import soundfile as sf
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

    def _convert_to_wav(self, audio_content: bytes, source_format: str) -> bytes:
        """
        오디오 파일을 WAV 형식으로 변환 (librosa 사용)

        Args:
            audio_content: 원본 오디오 바이너리 데이터
            source_format: 원본 파일 형식 (mp3, m4a, ogg 등)

        Returns:
            WAV 형식으로 변환된 바이너리 데이터
        """
        try:
            print(f"DEBUG: Converting {source_format} to WAV using librosa...")

            # 임시 파일 생성 (librosa는 파일 경로 필요)
            with tempfile.NamedTemporaryFile(suffix=f'.{source_format}', delete=False) as input_file:
                input_path = input_file.name
                input_file.write(audio_content)

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
                output_path = output_file.name

            try:
                # librosa로 오디오 로드 (자동으로 16kHz로 리샘플링)
                audio_data, sample_rate = librosa.load(input_path, sr=16000, mono=True)

                print(f"DEBUG: Loaded audio - sample rate: {sample_rate}Hz, duration: {len(audio_data)/sample_rate:.2f}s")

                # WAV 파일로 저장 (16-bit PCM)
                sf.write(output_path, audio_data, sample_rate, subtype='PCM_16')

                # 변환된 파일 읽기
                with open(output_path, 'rb') as f:
                    wav_content = f.read()

                print(f"DEBUG: Conversion successful. WAV size: {len(wav_content)} bytes")
                return wav_content

            finally:
                # 임시 파일 삭제
                Path(input_path).unlink(missing_ok=True)
                Path(output_path).unlink(missing_ok=True)

        except Exception as e:
            print(f"ERROR: Audio conversion failed: {str(e)}")
            raise Exception(f"오디오 변환 실패: {str(e)}")

    async def transcribe_audio(
        self, audio_file: BinaryIO, language: Optional[str] = "ko", filename: Optional[str] = None
    ) -> str:
        """
        음성 파일을 텍스트로 변환

        Args:
            audio_file: 업로드된 오디오 파일 객체
            language: 음성 언어 코드 (기본값: ko, 영어는 en-US)
            filename: 파일명 (인코딩 감지용, 선택 사항)

        Returns:
            변환된 텍스트

        Raises:
            Exception: API 호출 실패 시
        """
        try:
            client = self._get_client()

            # 오디오 파일 읽기
            content = audio_file.read()

            print(f"DEBUG: Original audio content size: {len(content)} bytes")
            print(f"DEBUG: Filename: {filename}")

            # 언어 코드 매핑 (ko -> ko-KR, en -> en-US)
            language_code_map = {
                "ko": "ko-KR",
                "en": "en-US",
                "ja": "ja-JP",
                "zh": "zh-CN",
            }
            language_code = language_code_map.get(language, f"{language}-KR")

            # 파일 확장자 기반 처리
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
            needs_conversion = False
            source_format = None

            if filename:
                filename_lower = filename.lower()
                # MP3, M4A 등은 WAV로 변환 필요
                if filename_lower.endswith('.mp3'):
                    needs_conversion = True
                    source_format = 'mp3'
                elif filename_lower.endswith('.m4a'):
                    needs_conversion = True
                    source_format = 'm4a'
                elif filename_lower.endswith('.wav'):
                    encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
                elif filename_lower.endswith('.flac'):
                    encoding = speech.RecognitionConfig.AudioEncoding.FLAC
                elif filename_lower.endswith('.ogg'):
                    encoding = speech.RecognitionConfig.AudioEncoding.OGG_OPUS
                elif filename_lower.endswith('.webm'):
                    encoding = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS

            # MP3/M4A를 WAV로 변환
            if needs_conversion:
                print(f"DEBUG: Converting {source_format} to WAV for better compatibility...")
                content = self._convert_to_wav(content, source_format)
                encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16

            print(f"DEBUG: Using encoding: {encoding}")
            print(f"DEBUG: Language code: {language_code}")
            print(f"DEBUG: Final audio size: {len(content)} bytes")

            # Google Speech-to-Text 설정
            audio = speech.RecognitionAudio(content=content)

            # 오디오 인코딩 설정
            config = speech.RecognitionConfig(
                encoding=encoding,
                sample_rate_hertz=16000,  # WAV 변환 시 16kHz로 설정
                language_code=language_code,
                enable_automatic_punctuation=True,  # 자동 문장 부호
                model="default",  # 기본 모델
                use_enhanced=False,  # 향상된 모델 사용 (비용 발생)
            )

            # 음성 인식 수행
            print("DEBUG: Calling Speech-to-Text API...")
            response = client.recognize(config=config, audio=audio)

            # 디버깅: 응답 확인
            print(f"DEBUG: Speech API response received")
            print(f"DEBUG: Number of results: {len(response.results)}")

            # 결과 추출
            if not response.results:
                print("WARNING: No results from Speech API - 오디오가 너무 짧거나, 인식 가능한 음성이 없거나, 인코딩 문제일 수 있습니다.")
                # 빈 결과 대신 의미 있는 에러 메시지 반환
                raise Exception(
                    "음성 인식 결과 없음: 오디오 파일이 너무 짧거나 음성이 명확하지 않을 수 있습니다. "
                    "파일 형식과 품질을 확인해주세요."
                )

            # 모든 결과를 합쳐서 반환
            transcript = " ".join(
                [result.alternatives[0].transcript for result in response.results]
            )

            print(f"DEBUG: Transcription success: {transcript}")
            return transcript

        except Exception as e:
            print(f"ERROR: Exception occurred: {str(e)}")
            print(f"ERROR: Exception type: {type(e).__name__}")
            raise Exception(f"음성 인식 실패: {str(e)}")


# 싱글톤 인스턴스
transcribe_service = TranscribeService()

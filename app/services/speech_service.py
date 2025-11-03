"""
Google Cloud Speech-to-Text API 서비스 (화자 분리 기능)
"""

from google.cloud import speech_v1p1beta1 as speech
import asyncio
import queue
import logging
from typing import AsyncGenerator, Dict, Optional
from app.config.settings import settings

logger = logging.getLogger(__name__)


class SpeechService:
    """Google Speech-to-Text API 서비스 (화자 분리 기능)"""

    def __init__(self):
        """Speech API 클라이언트 초기화"""
        try:
            self.client = speech.SpeechClient()
            logger.info("Speech API 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"Speech API 클라이언트 초기화 실패: {e}")
            raise

    def _create_config(
        self,
        language_code: str = "ko-KR",
        speaker_count: Optional[int] = None
    ) -> speech.RecognitionConfig:
        """
        인식 설정 생성

        Args:
            language_code: 언어 코드 (ko-KR, en-US 등)
            speaker_count: 예상 화자 수 (None이면 자동 감지)

        Returns:
            RecognitionConfig 객체
        """
        config = speech.RecognitionConfig(
            # 오디오 인코딩: 브라우저 MediaRecorder 기본 포맷
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,

            # 샘플링 레이트: 브라우저 기본값
            sample_rate_hertz=settings.speech_sample_rate,

            # 언어 설정
            language_code=language_code,

            # === 화자 분리 설정 (핵심!) ===
            enable_speaker_diarization=settings.enable_speaker_diarization,
            diarization_speaker_count=speaker_count,

            # 자동 문장부호 추가
            enable_automatic_punctuation=True,

            # 최적 모델 선택 (긴 오디오에 적합)
            model="latest_long",
        )

        logger.debug(f"Speech config 생성: lang={language_code}, speakers={speaker_count}")
        return config

    async def create_streaming_session(
        self,
        language_code: str = "ko-KR",
        speaker_count: Optional[int] = None
    ):
        """
        지속적인 Speech API 스트리밍 세션 생성

        Returns:
            SpeechStreamingSession 객체
        """
        config = self._create_config(language_code, speaker_count)
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=False  # 최종 결과만 받기
        )

        return SpeechStreamingSession(self.client, streaming_config)


class SpeechStreamingSession:
    """Google Speech API 지속 연결 관리"""

    def __init__(self, client, streaming_config):
        self.client = client
        self.streaming_config = streaming_config
        self.audio_queue = queue.Queue()  # 동기 큐로 변경
        self.is_running = False
        self.response_task = None

    def request_generator(self):
        """오디오 요청 제너레이터 (오디오만 전송)"""
        import sys
        print("[INFO] request_generator started", file=sys.stderr, flush=True)

        # 오디오만 전송 (config는 streaming_recognize의 첫 번째 인자로 전달)
        chunk_count = 0
        while self.is_running:
            try:
                # 큐에서 오디오 청크 가져오기 (0.5초 타임아웃)
                audio_chunk = self.audio_queue.get(timeout=0.5)
                if audio_chunk is not None:
                    chunk_count += 1
                    print(f"[SEND] Audio chunk to Speech API: {len(audio_chunk)} bytes (#{chunk_count})", file=sys.stderr, flush=True)
                    yield speech.StreamingRecognizeRequest(
                        audio_content=audio_chunk
                    )
            except queue.Empty:
                # 큐가 비어있으면 계속 대기
                if chunk_count == 0:
                    print(f"[WAIT] Waiting for first audio... (is_running={self.is_running})", file=sys.stderr, flush=True)
                continue

        print(f"[STOP] request_generator finished (total {chunk_count} chunks sent)", file=sys.stderr, flush=True)

    async def start_immediately(self, result_callback):
        """
        즉시 스트리밍 시작 (첫 오디오 대기 없음)

        Args:
            result_callback: 결과를 받을 async 함수 (result dict를 인자로 받음)
        """
        if self.is_running:
            logger.warning("이미 실행 중인 세션입니다")
            return

        self.is_running = True
        logger.info("🎙️ Speech API 스트리밍 세션 즉시 시작!")

        # 응답 처리 태스크 시작
        self.response_task = asyncio.create_task(
            self._process_responses(result_callback)
        )

    async def _process_responses(self, result_callback):
        """Speech API 응답 처리 (실시간 스트리밍)"""
        loop = asyncio.get_event_loop()

        try:
            # 제너레이터를 반환하는 함수
            def create_response_generator():
                """동기 API 호출 - 제너레이터 반환"""
                # v1p1beta1: streaming_config와 requests 2개 인자 필요
                return self.client.streaming_recognize(
                    self.streaming_config,
                    self.request_generator()
                )

            # 별도 스레드에서 제너레이터 생성
            response_generator = await loop.run_in_executor(None, create_response_generator)

            # 응답을 하나씩 실시간으로 처리
            def get_next_response():
                """다음 응답 가져오기 (블로킹)"""
                try:
                    return next(response_generator)
                except StopIteration:
                    return None

            while self.is_running:
                # 다음 응답 기다리기 (별도 스레드에서)
                response = await loop.run_in_executor(None, get_next_response)

                if response is None:
                    logger.info("Speech API 스트림 종료")
                    break

                if not response.results:
                    continue

                result = response.results[0]
                if not result.is_final:
                    continue

                alternative = result.alternatives[0]

                # 화자 정보 추출
                speaker_tag = None
                if alternative.words:
                    speaker_tag = alternative.words[0].speaker_tag

                result_data = {
                    "text": alternative.transcript.strip(),
                    "speaker_id": speaker_tag,
                    "confidence": alternative.confidence,
                    "is_final": result.is_final
                }

                logger.info(
                    f"✨ 실시간 인식: Speaker {speaker_tag}, "
                    f"텍스트: {alternative.transcript[:30]}..., "
                    f"신뢰도: {alternative.confidence:.2%}"
                )

                # 콜백 호출 (실시간으로 즉시 Sheets에 기록)
                await result_callback(result_data)

        except Exception as e:
            logger.error(f"스트리밍 응답 처리 실패: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("Speech API 응답 처리 종료")

    async def send_audio(self, audio_chunk: bytes):
        """오디오 청크를 큐에 추가 (스트림 시작 전에도 가능)"""
        # 동기 큐에 추가 (논블로킹)
        self.audio_queue.put(audio_chunk)
        queue_size = self.audio_queue.qsize()
        logger.info(f"✅ 오디오 청크 큐에 추가: {len(audio_chunk)} bytes (큐 크기: {queue_size})")

    async def stop(self):
        """스트리밍 종료"""
        logger.info("Speech API 스트리밍 세션 종료")
        self.is_running = False

        # 응답 처리 태스크 대기
        if self.response_task:
            try:
                await asyncio.wait_for(self.response_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("응답 처리 태스크 타임아웃")
                self.response_task.cancel()


# 싱글톤 인스턴스
speech_service = SpeechService()

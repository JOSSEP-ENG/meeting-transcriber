import json
import logging
import uuid
import base64
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config.settings import settings
from app.models.transcribe import SheetRecord
from app.services.sheets_service import sheets_service
from app.services.speech_service import speech_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# 활성 세션 관리
active_sessions: Dict[str, dict] = {}


@router.websocket("/test")
async def websocket_test(websocket: WebSocket):
    """Simple test endpoint"""
    await websocket.accept()
    await websocket.send_json({"message": "Test connection successful"})
    await websocket.close()


@router.websocket("/record")
async def websocket_record(websocket: WebSocket):
    """
    실시간 회의 녹음 WebSocket 엔드포인트

    클라이언트와 WebSocket 연결을 통해 오디오 스트림을 수신하고,
    회의 종료 시 전체 텍스트를 Google Sheets에 저장합니다.

    메시지 형식:
    - 클라이언트 -> 서버:
        {"type": "start", "language": "ko", "speaker": "홍길동", "meeting_title": "회의 제목"}
        {"type": "audio", "data": "<base64 encoded audio>"}
        {"type": "end"}

    - 서버 -> 클라이언트:
        {"type": "status", "message": "녹음 시작됨", "session_id": "..."}
        {"type": "transcription", "text": "변환된 텍스트"}
        {"type": "completed", "message": "회의가 저장되었습니다", "sheet_row": 123}
        {"type": "error", "message": "에러 메시지"}
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    import sys
    print(f"[VERSION 2.0] WebSocket 연결됨: session_id={session_id}", file=sys.stderr, flush=True)

    # 세션 데이터 초기화
    session = {
        "session_id": session_id,
        "language": "ko-KR",
        "speaker": settings.default_speaker,
        "meeting_title": None,
        "transcription_parts": [],  # 실시간으로 받은 텍스트 조각들
        "start_time": None,
        "sheet_id": None,  # 템플릿 시트 ID (파일 ID)
        "tab_id": None,  # 생성된 탭 ID
        "tab_name": None,  # 생성된 탭 이름
        "sheet_link": None,  # 탭 링크

        # 화자 관련 추가
        "participant_names": [],  # 참석자 명단 ["홍길동", "김철수"]
        "speaker_mapping": {},  # {1: "홍길동", 2: "김철수"}
        "last_speaker_id": None,  # 마지막 화자 Speaker ID
        "last_speaker_name": None,  # 마지막 화자 이름
        "unmapped_speakers": set(),  # 아직 매핑 안 된 Speaker ID들

        # Speech API 스트리밍 세션 (지속적 연결)
        "speech_session": None,  # SpeechStreamingSession 객체
        "websocket": websocket,  # WebSocket 객체 (콜백에서 사용)
    }
    active_sessions[session_id] = session

    try:
        while True:
            # 클라이언트로부터 메시지 수신
            message = await websocket.receive_text()
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "start":
                # 녹음 시작
                session["language"] = data.get("language", "ko-KR")
                session["speaker"] = data.get("speaker", settings.default_speaker)
                session["meeting_title"] = data.get("meeting_title", "제목없음")
                session["start_time"] = datetime.now()

                # 참석자 명단 파싱
                participants_str = data.get("participants", "")
                if participants_str:
                    session["participant_names"] = [
                        name.strip()
                        for name in participants_str.split(",")
                        if name.strip()
                    ]

                logger.info(
                    f"녹음 시작: session_id={session_id}, "
                    f"speaker={session['speaker']}, "
                    f"language={session['language']}, "
                    f"meeting_title={session['meeting_title']}, "
                    f"participants={session['participant_names']}"
                )

                # 템플릿 기반 회의록 시트 생성
                try:
                    meeting_date = session["start_time"].strftime("%Y-%m-%d")
                    meeting_time_start = session["start_time"].strftime("%H:%M")

                    import sys
                    print(f"DEBUG: Creating meeting sheet - title={session['meeting_title']}, date={meeting_date}", file=sys.stderr, flush=True)

                    sheet_info = await sheets_service.create_meeting_sheet(
                        meeting_title=session["meeting_title"],
                        meeting_date=meeting_date,
                        meeting_time=meeting_time_start  # 시작 시간만 우선 기록
                    )

                    session["sheet_id"] = sheet_info["file_id"]
                    session["tab_id"] = sheet_info.get("tab_id")
                    session["tab_name"] = sheet_info.get("tab_name")
                    session["sheet_link"] = sheet_info["web_link"]

                    logger.info(f"SUCCESS: Sheet created - ID={session['sheet_id']}, Link={session['sheet_link']}")

                    # Speech API 스트리밍 세션 생성 및 시작
                    speaker_count = len(session["participant_names"]) if session["participant_names"] else None
                    session["speech_session"] = await speech_service.create_streaming_session(
                        language_code=session["language"],
                        speaker_count=speaker_count
                    )

                    # 결과 콜백 정의
                    async def on_speech_result(result: dict):
                        """Speech API 결과를 받아서 처리"""
                        text = result["text"]
                        speaker_id = result["speaker_id"]

                        logger.info(f"인식 결과: Speaker {speaker_id}: {text}")

                        # 화자 매핑 확인
                        speaker_mapping = session["speaker_mapping"]

                        if speaker_id not in speaker_mapping:
                            # 아직 매핑 안 됨 → 클라이언트에 요청
                            session["unmapped_speakers"].add(speaker_id)

                            await websocket.send_json({
                                "type": "speaker_mapping_required",
                                "speaker_id": speaker_id,
                                "text": text,
                                "available_names": [
                                    name for name in session["participant_names"]
                                    if name not in speaker_mapping.values()
                                ]
                            })

                            # 임시로 Speaker X로 저장
                            current_speaker = f"Speaker {speaker_id}"
                        else:
                            # 이미 매핑됨
                            current_speaker = speaker_mapping[speaker_id]

                        # 시트에 기록
                        last_speaker = session.get("last_speaker_name")

                        sheet_result = await sheets_service.append_transcription_with_speaker(
                            sheet_id=session["sheet_id"],
                            tab_name=session["tab_name"],
                            text=text,
                            current_speaker=current_speaker,
                            last_speaker=last_speaker
                        )

                        # 세션 업데이트
                        session["last_speaker_id"] = speaker_id
                        session["last_speaker_name"] = current_speaker
                        session["transcription_parts"].append(text)

                        # 클라이언트에 확인
                        await websocket.send_json({
                            "type": "transcription_recorded",
                            "text": text,
                            "speaker": current_speaker,
                            "speaker_changed": sheet_result["speaker_changed"],
                            "row": sheet_result["row"]
                        })

                    # 콜백 저장 (첫 오디오 도착 시 스트림 시작)
                    session["speech_callback"] = on_speech_result
                    session["speech_started"] = False  # 스트림 시작 여부
                    logger.info("Speech API 스트리밍 세션 준비 완료 (첫 오디오 대기 중)")

                    response_data = {
                        "type": "status",
                        "message": "녹음이 시작되었습니다",
                        "session_id": session_id,
                        "sheet_id": session["sheet_id"],
                        "sheet_link": session["sheet_link"],
                    }
                    logger.info(f"Sending response: {response_data}")
                    await websocket.send_json(response_data)

                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"ERROR: Sheet creation failed")
                    logger.error(f"ERROR: {str(e)}")
                    logger.error(f"TRACEBACK: {error_details}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"시트 생성 실패: {str(e)}",
                    })

            elif message_type == "audio":
                # 오디오 청크 수신 (Base64 인코딩됨)
                audio_base64 = data.get("data")
                import sys
                print(f"[AUDIO] Received audio message, base64 length: {len(audio_base64) if audio_base64 else 0}", file=sys.stderr, flush=True)

                if audio_base64 and session.get("speech_session"):
                    # Base64 디코딩
                    try:
                        audio_bytes = base64.b64decode(audio_base64)
                        print(f"[AUDIO] Decoded audio chunk: {len(audio_bytes)} bytes", file=sys.stderr, flush=True)

                        # 첫 오디오 도착 시 스트림 시작
                        if not session.get("speech_started"):
                            print("[START] First audio arrived! Starting Speech API stream...", file=sys.stderr, flush=True)
                            session["speech_started"] = True

                            # 중요: 첫 오디오를 먼저 큐에 추가 (타임아웃 방지)
                            await session["speech_session"].send_audio(audio_bytes)
                            print(f"[OK] First audio added to queue: {len(audio_bytes)} bytes", file=sys.stderr, flush=True)

                            # 스트림 시작 (비동기 태스크로 실행)
                            speech_callback = session.get("speech_callback")
                            if speech_callback:
                                await session["speech_session"].start_immediately(speech_callback)
                            else:
                                print("[ERROR] speech_callback not found!", file=sys.stderr, flush=True)
                        else:
                            # 이후 오디오는 계속 큐에 추가
                            await session["speech_session"].send_audio(audio_bytes)

                    except Exception as e:
                        print(f"[ERROR] Audio processing failed: {e}", file=sys.stderr, flush=True)
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[WARNING] Audio processing skipped - base64={bool(audio_base64)}, session={bool(session.get('speech_session'))}", file=sys.stderr, flush=True)

            elif message_type == "speaker_mapping":
                # 화자 매핑
                speaker_id = data.get("speaker_id")
                speaker_name = data.get("speaker_name")

                if speaker_id is not None and speaker_name:
                    session["speaker_mapping"][speaker_id] = speaker_name
                    session["unmapped_speakers"].discard(speaker_id)

                    logger.info(f"화자 매핑: Speaker {speaker_id} = {speaker_name}")

                    # 레이블 업데이트
                    try:
                        await sheets_service.update_speaker_labels(
                            sheet_id=session["sheet_id"],
                            tab_name=session["tab_name"],
                            old_label=f"Speaker {speaker_id}",
                            new_label=speaker_name
                        )
                    except Exception as e:
                        logger.error(f"레이블 업데이트 실패: {e}")

                    await websocket.send_json({
                        "type": "speaker_mapped",
                        "speaker_id": speaker_id,
                        "speaker_name": speaker_name
                    })

            elif message_type == "transcription":
                # 클라이언트가 직접 변환한 텍스트를 전송하는 경우
                # (브라우저의 Web Speech API 등 사용 시)
                text = data.get("text", "").strip()
                if text and session.get("sheet_id") and session.get("tab_name"):
                    session["transcription_parts"].append(text)
                    print(f"텍스트 수신: session_id={session_id}, text={text}")

                    # 실시간으로 시트에 기록 (C13부터)
                    try:
                        row_number = await sheets_service.append_transcription_to_sheet(
                            sheet_id=session["sheet_id"],
                            tab_name=session["tab_name"],
                            transcription=text
                        )

                        # 클라이언트에 확인 전송
                        await websocket.send_json({
                            "type": "transcription_received",
                            "text": text,
                            "row": row_number,
                        })

                    except Exception as e:
                        print(f"실시간 녹취 기록 실패: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"녹취 기록 실패: {str(e)}",
                        })

            elif message_type == "end":
                # 녹음 종료
                print(f"녹음 종료: session_id={session_id}")

                # 전체 텍스트 병합
                full_transcription = " ".join(session["transcription_parts"])

                if not full_transcription.strip():
                    await websocket.send_json({
                        "type": "error",
                        "message": "녹음된 내용이 없습니다",
                    })
                    continue

                # 이미 실시간으로 C13부터 기록되었으므로 완료 메시지만 전송
                await websocket.send_json({
                    "type": "completed",
                    "message": "회의 내용이 성공적으로 저장되었습니다",
                    "sheet_id": session.get("sheet_id"),
                    "sheet_link": session.get("sheet_link"),
                    "transcription": full_transcription,
                    "transcription_count": len(session["transcription_parts"]),
                })

                print(f"회의 종료 완료: session_id={session_id}, sheet={session.get('sheet_id')}")

                # 세션 정리
                session["transcription_parts"].clear()

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"알 수 없는 메시지 타입: {message_type}",
                })

    except WebSocketDisconnect:
        print(f"WebSocket 연결 종료: session_id={session_id}")
    except Exception as e:
        print(f"WebSocket 에러: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"서버 에러: {str(e)}",
            })
        except:
            pass
    finally:
        # Speech API 스트리밍 세션 종료
        if session_id in active_sessions:
            session = active_sessions[session_id]
            if session.get("speech_session"):
                try:
                    await session["speech_session"].stop()
                    logger.info(f"Speech API 스트림 종료: session_id={session_id}")
                except Exception as e:
                    logger.error(f"Speech API 스트림 종료 실패: {e}")

            del active_sessions[session_id]
        print(f"세션 정리 완료: session_id={session_id}")


@router.get("/sessions")
async def get_active_sessions():
    """활성 세션 목록 조회 (디버깅용)"""
    return {
        "active_sessions": len(active_sessions),
        "sessions": [
            {
                "session_id": session["session_id"],
                "speaker": session["speaker"],
                "start_time": session["start_time"].isoformat() if session["start_time"] else None,
                "transcription_count": len(session["transcription_parts"]),
            }
            for session in active_sessions.values()
        ],
    }

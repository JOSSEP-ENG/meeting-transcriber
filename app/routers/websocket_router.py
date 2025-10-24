import json
import uuid
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config.settings import settings
from app.models.transcribe import SheetRecord
from app.services.sheets_service import sheets_service

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# 활성 세션 관리
active_sessions: Dict[str, dict] = {}


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
    print(f"WebSocket 연결됨: session_id={session_id}")

    # 세션 데이터 초기화
    session = {
        "session_id": session_id,
        "language": "ko",
        "speaker": settings.default_speaker,
        "meeting_title": None,
        "transcription_parts": [],  # 실시간으로 받은 텍스트 조각들
        "start_time": None,
        "audio_buffer": [],  # 오디오 청크 버퍼
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
                session["language"] = data.get("language", "ko")
                session["speaker"] = data.get("speaker", settings.default_speaker)
                session["meeting_title"] = data.get("meeting_title")
                session["start_time"] = datetime.now()

                print(
                    f"녹음 시작: session_id={session_id}, "
                    f"speaker={session['speaker']}, "
                    f"language={session['language']}"
                )

                await websocket.send_json({
                    "type": "status",
                    "message": "녹음이 시작되었습니다",
                    "session_id": session_id,
                })

            elif message_type == "audio":
                # 오디오 청크 수신
                # 실제 구현에서는 이 부분에서 Google Speech Streaming API를 호출할 수 있습니다
                # 현재는 버퍼에 저장만 합니다
                audio_data = data.get("data")
                if audio_data:
                    session["audio_buffer"].append(audio_data)
                    print(f"오디오 청크 수신: session_id={session_id}, chunks={len(session['audio_buffer'])}")

            elif message_type == "transcription":
                # 클라이언트가 직접 변환한 텍스트를 전송하는 경우
                # (브라우저의 Web Speech API 등 사용 시)
                text = data.get("text", "").strip()
                if text:
                    session["transcription_parts"].append(text)
                    print(f"텍스트 수신: session_id={session_id}, text={text}")

                    # 클라이언트에 확인 전송
                    await websocket.send_json({
                        "type": "transcription_received",
                        "text": text,
                    })

            elif message_type == "end":
                # 녹음 종료 및 저장
                print(f"녹음 종료: session_id={session_id}")

                # 전체 텍스트 병합
                full_transcription = " ".join(session["transcription_parts"])

                if not full_transcription.strip():
                    await websocket.send_json({
                        "type": "error",
                        "message": "녹음된 내용이 없습니다",
                    })
                    continue

                # Google Sheets에 저장
                now = datetime.now()
                sheet_record = SheetRecord(
                    timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
                    speaker=session["speaker"],
                    transcription=full_transcription,
                    meeting_title=session["meeting_title"],
                )

                try:
                    row_number = await sheets_service.append_record(sheet_record)

                    await websocket.send_json({
                        "type": "completed",
                        "message": "회의 내용이 성공적으로 저장되었습니다",
                        "sheet_row": row_number,
                        "transcription": full_transcription,
                    })

                    print(f"시트에 저장 완료: session_id={session_id}, row={row_number}")

                except Exception as e:
                    print(f"시트 저장 실패: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"저장 실패: {str(e)}",
                    })

                # 세션 정리
                session["transcription_parts"].clear()
                session["audio_buffer"].clear()

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
        # 세션 정리
        if session_id in active_sessions:
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

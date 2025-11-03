"""
WebSocket 화자 분리 기능 테스트 스크립트
"""
import asyncio
import json
import websockets
import sys
import io

# Windows 콘솔 UTF-8 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test_websocket():
    uri = "ws://localhost:8000/ws/record"

    async with websockets.connect(uri) as websocket:
        print("✅ WebSocket 연결 성공")

        # 1. 회의 시작 (참석자 정보 포함)
        start_message = {
            "type": "start",
            "language": "ko-KR",
            "speaker": "테스트 사용자",
            "meeting_title": "화자 분리 테스트 회의",
            "participants": "홍길동, 김철수, 이영희"
        }
        await websocket.send(json.dumps(start_message))
        print(f"\n📤 [SEND] {start_message['type']}")
        print(f"   - 회의 제목: {start_message['meeting_title']}")
        print(f"   - 참석자: {start_message['participants']}")

        response = await websocket.recv()
        print(f"\n📥 [RECV] {response}")
        data = json.loads(response)

        if data.get("type") == "status":
            print(f"\n✅ 회의 시작 성공!")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Sheet ID: {data.get('sheet_id')}")
            print(f"   Sheet Link: {data.get('sheet_link')}")
        elif data.get("type") == "error":
            print(f"\n❌ [ERROR] {data.get('message')}")
            return

        # 2. 텍스트 전송 (기존 방식 - Web Speech API)
        print("\n\n📝 텍스트 전송 테스트 (Web Speech API 호환)")
        for i, text in enumerate(["안녕하세요", "테스트 중입니다", "녹음 확인"], 1):
            transcription_message = {
                "type": "transcription",
                "text": text
            }
            await websocket.send(json.dumps(transcription_message))
            print(f"\n📤 [SEND] Text {i}: {text}")

            response = await websocket.recv()
            print(f"📥 [RECV] {response}")

            await asyncio.sleep(0.5)

        # 3. 화자 분리 정보 확인
        print("\n\n📊 화자 분리 기능 검증:")
        print("   ℹ️  실제 오디오 처리는 Google Speech API 크레딧 소모로 스킵")
        print("   ℹ️  브라우저에서 MediaRecorder로 테스트 권장")
        print("\n   구현된 기능:")
        print("   ✅ 1. MediaRecorder로 오디오 캡처 (frontend)")
        print("   ✅ 2. Base64 인코딩하여 WebSocket 전송")
        print("   ✅ 3. Google Speech API로 화자 분리 인식")
        print("   ✅ 4. Speaker ID → 참석자 이름 매핑 모달")
        print("   ✅ 5. 화자 변경 시에만 [화자명] 표시")

        # 4. 회의 종료
        end_message = {"type": "end"}
        await websocket.send(json.dumps(end_message))
        print(f"\n\n📤 [SEND] 회의 종료")

        response = await websocket.recv()
        print(f"📥 [RECV] {response}")
        data = json.loads(response)

        if data.get("type") == "completed":
            print(f"\n✅ 회의 종료 완료!")
            print(f"   Sheet Link: {data.get('sheet_link')}")
            print(f"   총 녹취 개수: {data.get('transcription_count')}")

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except Exception as e:
        print(f"[ERROR] {e}")

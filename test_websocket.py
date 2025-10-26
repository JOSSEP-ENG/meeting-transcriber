"""
WebSocket 테스트 스크립트
"""
import asyncio
import json
import websockets

async def test_websocket():
    uri = "ws://localhost:8000/ws/record"

    async with websockets.connect(uri) as websocket:
        print("[OK] WebSocket connected")

        # 1. 회의 시작
        start_message = {
            "type": "start",
            "language": "ko",
            "speaker": "Test User",
            "meeting_title": "Test Meeting"
        }
        await websocket.send(json.dumps(start_message))
        print(f"[SEND] {start_message}")

        response = await websocket.recv()
        print(f"[RECV] {response}")
        data = json.loads(response)

        if data.get("type") == "status":
            print(f"[OK] Meeting started!")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Sheet ID: {data.get('sheet_id')}")
            print(f"   Sheet Link: {data.get('sheet_link')}")
            print(f"   Full response: {data}")
        elif data.get("type") == "error":
            print(f"[ERROR] {data.get('message')}")
            return

        # 2. 텍스트 전송
        for i, text in enumerate(["Hello", "Test in progress", "Recording check"], 1):
            transcription_message = {
                "type": "transcription",
                "text": text
            }
            await websocket.send(json.dumps(transcription_message))
            print(f"\n[SEND] Text {i}: {text}")

            response = await websocket.recv()
            print(f"[RECV] {response}")

            await asyncio.sleep(1)

        # 3. 회의 종료
        end_message = {"type": "end"}
        await websocket.send(json.dumps(end_message))
        print(f"\n[SEND] {end_message}")

        response = await websocket.recv()
        print(f"[RECV] {response}")
        data = json.loads(response)

        if data.get("type") == "completed":
            print(f"\n[OK] Meeting completed!")
            print(f"   Sheet Link: {data.get('sheet_link')}")
            print(f"   Transcription Count: {data.get('transcription_count')}")

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except Exception as e:
        print(f"[ERROR] {e}")

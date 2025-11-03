# -*- coding: utf-8 -*-
"""
WebSocket debug script
"""
import asyncio
import json
import websockets
import sys
import io

# Windows console UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def debug_ws():
    uri = "ws://localhost:8000/ws/record"

    try:
        async with websockets.connect(uri) as ws:
            print("[OK] WebSocket connected")

            # Send start message
            start_msg = {
                "type": "start",
                "meeting_title": "Debug Test",
                "participants": "Tester1",
                "language": "ko-KR"
            }
            await ws.send(json.dumps(start_msg))
            print(f"[SEND] {start_msg}")

            # Wait for response (10s timeout)
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                print(f"[RECV] {response}")
            except asyncio.TimeoutError:
                print("[TIMEOUT] No response for 10 seconds")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_ws())

import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({"type": "refresh_firmware_status", "ip": "192.168.0.103"}))
        while True:
            msg = await websocket.recv()
            print("Received:", msg)

asyncio.run(test())

import asyncio
from fastapi import FastAPI
import uvicorn
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead
import sys

app = FastAPI()

@app.get("/test")
async def test_smp():
    print("Testing SMP inside FastAPI!")
    client = SMPClient(SMPUDPTransport(mtu=1200), "192.168.0.103", timeout_s=2.0)
    try:
        await client.connect()
        response = await client.request(ImageStatesRead())
        print("Response:", response)
        return {"status": "ok"}
    except Exception as e:
        print("Exception:", e)
        return {"status": "error", "error": str(e)}
    finally:
        if 'client' in locals():
            await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        uvicorn.run(app, host="127.0.0.1", port=8001)

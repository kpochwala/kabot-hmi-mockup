import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def test():
    client = SMPClient(SMPUDPTransport(mtu=1200), "192.168.0.103", timeout_s=2.0)
    print("connecting...")
    try:
        await client.connect()
        print("requesting...")
        await client.request(ImageStatesRead())
    except Exception as e:
        print("Exception:", e)
    
    print("disconnecting...")
    try:
        await asyncio.wait_for(client.disconnect(), timeout=2.0)
        print("disconnected.")
    except Exception as e:
        print("disconnect timed out/failed:", e)

asyncio.run(test())

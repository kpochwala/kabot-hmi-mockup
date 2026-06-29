import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def test():
    client = SMPClient(SMPUDPTransport(mtu=1200), "192.168.0.103", timeout_s=2.0)
    print("connecting...")
    try:
        await client.connect()
    except Exception as e:
        print("Connect exception:", e)
    
    print("disconnecting...")
    await client.disconnect()
    print("disconnected.")

asyncio.run(test())

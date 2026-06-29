import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def test():
    client = SMPClient(SMPUDPTransport(mtu=1200), "192.168.0.103", timeout_s=2.0)
    print("connecting...")
    await client.connect()
    print("requesting...")
    response = await client.request(ImageStatesRead())
    print("Response:", response)

asyncio.run(test())

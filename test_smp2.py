import asyncio
import socket
import time
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def block_loop():
    while True:
        # Simulate sock.recvfrom(2048) with 0.5s timeout
        time.sleep(0.5)
        await asyncio.sleep(0.1)

async def test():
    client = SMPClient(SMPUDPTransport(), "192.168.0.103", timeout_s=2.0)
    print("connecting...")
    await client.connect()
    print("requesting...")
    response = await client.request(ImageStatesRead())
    print("Got response")

async def main():
    asyncio.create_task(block_loop())
    await asyncio.sleep(0.5)
    await test()

asyncio.run(main())

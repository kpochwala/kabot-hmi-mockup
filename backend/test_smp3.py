import asyncio
import socket
import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models'))
import state_control_msg_pb2 as pb2

from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def discovery_spam():
    req = pb2.Bonjour()
    req.hmi_port = 30011
    req.claim = False
    req.release = False
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(req.SerializeToString(), ('255.255.255.255', 30012))
            sock.sendto(req.SerializeToString(), ('192.168.0.255', 30012))
        await asyncio.sleep(0.1)

async def test():
    client = SMPClient(SMPUDPTransport(), "192.168.0.103", timeout_s=2.0)
    print("connecting...")
    await client.connect()
    print("requesting...")
    response = await client.request(ImageStatesRead())
    print("Got response:", response)

async def main():
    spam = asyncio.create_task(discovery_spam())
    await asyncio.sleep(0.5)
    try:
        await test()
    except Exception as e:
        print("Test failed:", e)
    spam.cancel()

asyncio.run(main())

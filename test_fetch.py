import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
async def run():
    client = SMPClient(SMPUDPTransport(mtu=256), '192.168.0.100', timeout_s=3.0)
    await client.connect()
    r = await asyncio.get_running_loop().run_in_executor(None, client.image_management.image_state.read)
    print(r.images[0].hash.hex())
asyncio.run(run())

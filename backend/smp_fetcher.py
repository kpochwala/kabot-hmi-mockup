import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def fetch_firmware_status(ip: str) -> dict:
    # We explicitly set MTU to 1200 to ensure reliable SMP responses over UDP without triggering Zephyr stack overflow.
    client = SMPClient(SMPUDPTransport(mtu=1200), ip, timeout_s=3.0)
    try:
        await client.connect()
        
        response = None
        for attempt in range(10):
            try:
                response = await client.request(ImageStatesRead())
                break
            except Exception as e:
                if attempt == 9:
                    raise
                await asyncio.sleep(0.5)
        
        if hasattr(response, 'images'):
            images = []
            for img in response.images:
                images.append({
                    'image': getattr(img, 'image', 0),
                    'slot': getattr(img, 'slot', 0),
                    'version': getattr(img, 'version', ''),
                    'hash': img.hash.hex() if hasattr(img, 'hash') and img.hash else '',
                    'bootable': getattr(img, 'bootable', False),
                    'pending': getattr(img, 'pending', False),
                    'confirmed': getattr(img, 'confirmed', False),
                    'active': getattr(img, 'active', False),
                    'permanent': getattr(img, 'permanent', False),
                })
            return {"data": images}
        else:
            raise ValueError("Unexpected response format")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing IP"}))
        sys.exit(1)
    
    async def _run():
        try:
            res = await fetch_firmware_status(sys.argv[1])
            print(json.dumps(res))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    
    asyncio.run(_run())

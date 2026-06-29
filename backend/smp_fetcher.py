import sys
import json
import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead

async def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing IP"}))
        return
    ip = sys.argv[1]
    
    # We use exactly what smpmgr uses internally, with default MTU to be identical to smpmgr CLI.
    # smpmgr default MTU is 4096 (actually depends on transport, but we just omit to use default).
    try:
        client = SMPClient(SMPUDPTransport(mtu=1200), ip, timeout_s=3.0)
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
            print(json.dumps({"data": images}))
        else:
            print(json.dumps({"error": "Unexpected response format"}))
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        if 'client' in locals():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

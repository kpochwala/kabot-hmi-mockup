import sys
import json
import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient

async def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Missing IP or Firmware Path"}))
        return
    ip = sys.argv[1]
    fw_path = sys.argv[2]
    
    try:
        with open(fw_path, 'rb') as f:
            image_data = f.read()
    except Exception as e:
        print(json.dumps({"error": f"Failed to read firmware: {e}"}))
        return

    total_size = len(image_data)
    if total_size == 0:
        print(json.dumps({"error": "Firmware file is empty"}))
        return

    try:
        # Use 256 MTU as negotiated with the user to prevent Zephyr stack overflow
        client = SMPClient(SMPUDPTransport(mtu=256), ip, timeout_s=3.0)
        await client.connect()
        
        # Upload generator yields the current offset
        async for offset in client.upload(image_data, slot=1):
            progress = (offset / total_size) * 100
            print(json.dumps({"progress": progress, "offset": offset, "total": total_size}), flush=True)
            
        # 100% completion
        print(json.dumps({"progress": 100.0, "offset": total_size, "total": total_size}), flush=True)
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        if 'client' in locals():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

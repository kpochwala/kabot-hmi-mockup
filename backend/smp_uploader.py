import asyncio
from typing import Callable, Awaitable
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient

async def upload_firmware(ip: str, fw_path: str, progress_callback: Callable[[float], Awaitable[None]] = None):
    try:
        with open(fw_path, 'rb') as f:
            image_data = f.read()
    except Exception as e:
        raise RuntimeError(f"Failed to read firmware: {e}")

    total_size = len(image_data)
    if total_size == 0:
        raise ValueError("Firmware file is empty")

    # We explicitly set MTU to 1200 to maximize throughput while avoiding firmware-side Wi-Fi fragmentation/stack overflow.
    client = SMPClient(SMPUDPTransport(mtu=1200), ip, timeout_s=3.0)
    try:
        await client.connect()
        
        # Upload generator yields the current offset
        async for offset in client.upload(image_data, slot=1):
            if progress_callback:
                progress = (offset / total_size) * 100
                await progress_callback(progress)
            
        # 100% completion
        if progress_callback:
            await progress_callback(100.0)
            
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Missing IP or Firmware Path"}))
        sys.exit(1)
        
    async def _print_progress(progress):
        print(json.dumps({"progress": progress}), flush=True)
        
    async def _run():
        try:
            await upload_firmware(sys.argv[1], sys.argv[2], _print_progress)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            
    asyncio.run(_run())

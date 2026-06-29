import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesWrite
from smpclient.requests.os_management import ResetWrite

async def run_smp_action(ip: str, action: str, hash_hex: str = "") -> dict:
    if action not in ("pending", "reset", "confirm", "boot"):
        raise ValueError(f"Unknown action: {action}")

    try:
        hash_bytes = bytes.fromhex(hash_hex) if hash_hex and hash_hex != "none" else b''
    except ValueError as e:
        raise ValueError(f"Invalid hash: {e}")

    client = SMPClient(SMPUDPTransport(mtu=1200), ip, timeout_s=3.0)
    try:
        await client.connect()
        
        async def do_request(req):
            for attempt in range(10):
                try:
                    return await client.request(req)
                except Exception as e:
                    if attempt == 9:
                        raise
                    await asyncio.sleep(0.5)

        if action == "pending":
            await do_request(ImageStatesWrite(hash=hash_bytes, confirm=False))
            return {"success": True, "action": "pending"}
            
        elif action == "reset":
            await do_request(ResetWrite())
            return {"success": True, "action": "reset"}
            
        elif action == "boot":
            # Set the image as pending (test)
            await do_request(ImageStatesWrite(hash=hash_bytes, confirm=False))
            # Reboot the device
            await do_request(ResetWrite())
            return {"success": True, "action": "boot"}
        
        elif action == "confirm":
            # Confirm the active image
            await do_request(ImageStatesWrite(hash=hash_bytes, confirm=True))
            return {"success": True, "action": "confirm"}
            
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: smp_action.py <ip> <action> <hash_hex>"}))
        sys.exit(1)
        
    async def _run():
        try:
            res = await run_smp_action(sys.argv[1], sys.argv[2], sys.argv[3])
            print(json.dumps(res))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            
    asyncio.run(_run())

import sys
import json
import asyncio
from smpclient.transport.udp import SMPUDPTransport
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesWrite
from smpclient.requests.os_management import ResetWrite

async def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: smp_action.py <ip> <action> <hash_hex>"}))
        return
    ip = sys.argv[1]
    action = sys.argv[2]
    hash_hex = sys.argv[3]
    
    if action not in ("pending", "reset", "confirm", "boot"):
        print(json.dumps({"error": f"Unknown action: {action}"}))
        return

    try:
        hash_bytes = bytes.fromhex(hash_hex) if hash_hex and hash_hex != "none" else b''
    except ValueError as e:
        print(json.dumps({"error": f"Invalid hash: {e}"}))
        return

    try:
        client = SMPClient(SMPUDPTransport(mtu=1200), ip, timeout_s=3.0)
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
            print(json.dumps({"success": True, "action": "pending"}))
            
        elif action == "reset":
            await do_request(ResetWrite())
            print(json.dumps({"success": True, "action": "reset"}))
            
        elif action == "boot":
            # Set the image as pending (test)
            await do_request(ImageStatesWrite(hash=hash_bytes, confirm=False))
            # Reboot the device
            await do_request(ResetWrite())
            print(json.dumps({"success": True, "action": "boot"}))
        
        elif action == "confirm":
            # Confirm the active image
            await do_request(ImageStatesWrite(hash=hash_bytes, confirm=True))
            print(json.dumps({"success": True, "action": "confirm"}))
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        if 'client' in locals():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

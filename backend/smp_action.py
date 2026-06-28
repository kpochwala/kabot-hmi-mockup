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
    
    if action not in ("boot", "confirm"):
        print(json.dumps({"error": f"Unknown action: {action}"}))
        return

    try:
        hash_bytes = bytes.fromhex(hash_hex)
    except ValueError as e:
        print(json.dumps({"error": f"Invalid hash: {e}"}))
        return

    try:
        client = SMPClient(SMPUDPTransport(mtu=256), ip, timeout_s=3.0)
        await client.connect()
        
        if action == "boot":
            # Set the image as pending (test)
            await client.request(ImageStatesWrite(hash=hash_bytes, confirm=False))
            # Reboot the device
            await client.request(ResetWrite())
            print(json.dumps({"success": True, "action": "boot"}))
        
        elif action == "confirm":
            # Confirm the active image
            await client.request(ImageStatesWrite(hash=hash_bytes, confirm=True))
            print(json.dumps({"success": True, "action": "confirm"}))
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        if 'client' in locals():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

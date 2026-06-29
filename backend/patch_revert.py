import re

with open("backend/main.py", "r") as f:
    content = f.read()

# Fix fetch_firmware_status
content = re.sub(
    r"(was_claimed = \(udp_target_ip == ip\)\s+)await _broadcast_log\('HMI', f\"Silencing \{ip\} telemetry to safely perform SMP operation\"\)",
    r"\1if was_claimed:\n                await _broadcast_log('HMI', f\"Temporarily releasing {ip} to safely perform SMP operation\")",
    content
)

# Fix flash_firmware
content = re.sub(
    r"(try:\n\s+rel_req = pb2.Bonjour\(\)\n\s+rel_req.hmi_port = UDP_STATE_PORT\n\s+rel_req.release = True\n\s+with socket.socket\(socket.AF_INET, socket.SOCK_DGRAM\) as rel_sock:\n\s+rel_sock.bind\(\(\"0.0.0.0\", 0\)\)\n\s+rel_sock.settimeout\(0.5\)\n\s+rel_sock.sendto\(rel_req.SerializeToString\(\), \(ip, 30012\)\)\n\s+try:\n\s+rel_sock.recvfrom\(2048\)\n\s+except TimeoutError:\n\s+pass\n\s+except Exception as e:\n\s+await _broadcast_log\('HMI', f\"Error during temp release: \{e\}\"\))",
    r"    \1",
    content
)

# We need to properly indent the try/except block if we put it under an 'if was_claimed:'

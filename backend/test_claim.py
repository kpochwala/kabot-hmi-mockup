import socket
import state_control_msg_pb2 as pb2

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
req = pb2.Bonjour()
req.hmi_port = 30011
req.claim = True
req.release = False
sock.sendto(req.SerializeToString(), ("127.0.0.1", 30012))
print("Sent claim to 127.0.0.1:30012")

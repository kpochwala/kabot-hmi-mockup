import psutil
import ipaddress
import socket

interfaces = psutil.net_if_addrs()
subnets = []
local_ips = set()
for iface_name, addrs in interfaces.items():
    for addr in addrs:
        if addr.family == socket.AF_INET:
            ip = addr.address
            local_ips.add(ip)
            netmask = addr.netmask
            if netmask:
                try:
                    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                    subnets.append(network)
                    print(f"{iface_name}: {ip}/{netmask} -> {network} ({network.num_addresses} IPs)")
                except Exception as e:
                    print(e)

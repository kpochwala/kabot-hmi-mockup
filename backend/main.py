import asyncio
import contextlib
import io
import inspect
from pathlib import Path
import os
import socket
import traceback
import json
import ipaddress
import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import state_control_msg_pb2 as pb2
from models import RobotState, RobotControl, Vector2, Vector3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

UDP_STATE_PORT = 30011
UDP_CONTROL_PORT = 30010
UDP_TARGET_IP = '172.20.10.2'
udp_target_ip = UDP_TARGET_IP

DEFAULT_SCRIPTS_DIR = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'kabot-hmi' / 'scripts'
scripts_dir = DEFAULT_SCRIPTS_DIR

current_user_code = None
current_user_callable = None
active_connections = []


def _build_user_callable(code: str):
    compiled = compile(code, '<user_code>', 'exec')
    local_env = {
        'RobotState': RobotState,
        'RobotControl': RobotControl,
        'Vector2': Vector2,
        'Vector3': Vector3,
    }
    exec(compiled, local_env)
    user_func = local_env.get('control')
    if user_func is None:
        raise ValueError("Function 'control' is not defined")
    if not callable(user_func):
        raise ValueError("'control' is not callable")
    param_count = len(inspect.signature(user_func).parameters)
    if param_count < 2:
        raise ValueError("'control' must accept at least two parameters: state and control")
    return user_func


def _normalize_control(result_ctrl: object) -> RobotControl:
    if result_ctrl is None:
        raise ValueError("control(...) returned None")
    effort = getattr(result_ctrl, 'effort', None)
    if effort is None:
        raise ValueError("control(...) return value is missing effort")
    x = getattr(effort, 'x', None)
    y = getattr(effort, 'y', None)
    if x is None or y is None:
        raise ValueError("control(...) return value is missing effort.x or effort.y")
    return RobotControl(effort=Vector2(float(x), float(y)))


async def _send_json(conn: WebSocket, payload: dict):
    await conn.send_text(json.dumps(payload))


async def _broadcast_json(payload: dict):
    stale = []
    data = json.dumps(payload)
    for conn in active_connections:
        try:
            await conn.send_text(data)
        except Exception:
            stale.append(conn)
    for conn in stale:
        if conn in active_connections:
            active_connections.remove(conn)


async def _set_runtime_active(active: bool):
    await _broadcast_json({'type': 'runtime_status', 'active': active})


def _resolve_scripts_dir(path_value: str | None = None) -> Path:
    base = scripts_dir if path_value is None else Path(path_value.strip()).expanduser()
    if not base.is_absolute():
        base = (Path(__file__).resolve().parent / base).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _normalize_script_name(name: str) -> str:
    raw = (name or '').strip()
    if not raw:
        raise ValueError('Script name cannot be empty')
    if '/' in raw or '\\' in raw:
        raise ValueError('Script name must not include path separators')
    stem = raw[:-3] if raw.lower().endswith('.py') else raw
    stem = stem.strip()
    if not stem:
        raise ValueError('Script name cannot be empty')
    if '..' in stem:
        raise ValueError('Script name cannot contain ..')
    return f'{stem}.py'


def _list_scripts() -> list[str]:
    folder = _resolve_scripts_dir()
    return sorted(p.name for p in folder.glob('*.py') if p.is_file())


def _read_script(name: str) -> tuple[str, str]:
    file_name = _normalize_script_name(name)
    file_path = _resolve_scripts_dir() / file_name
    if not file_path.exists():
        raise FileNotFoundError(f'Script not found: {file_name}')
    return file_name, file_path.read_text(encoding='utf-8')


def _write_script(name: str, code: str) -> str:
    file_name = _normalize_script_name(name)
    file_path = _resolve_scripts_dir() / file_name
    file_path.write_text(code, encoding='utf-8')
    return file_name

def decode_state(data: bytes) -> RobotState:
    msg = pb2.State()
    msg.ParseFromString(data)
    
    stamps = {
        'state': msg.header.stamp,
        'distance': msg.distance.header.stamp,
        'effort': msg.effort.header.stamp,
        'accel': msg.linear_acceleration.header.stamp,
        'gyro': msg.angular_velocity.header.stamp,
        'mag': msg.magnetic_field.header.stamp,
        'light_left': msg.light_left.header.stamp,
        'light_right': msg.light_right.header.stamp,
        'current_left': msg.current_left.header.stamp,
        'bus_voltage_left': msg.bus_voltage_left.header.stamp,
        'power_left': msg.power_left.header.stamp,
        'current_right': msg.current_right.header.stamp,
        'bus_voltage_right': msg.bus_voltage_right.header.stamp,
        'power_right': msg.power_right.header.stamp,
        'current_supply': msg.current_supply.header.stamp,
        'bus_voltage_supply': msg.bus_voltage_supply.header.stamp,
        'power_supply': msg.power_supply.header.stamp,
    }
    
    return RobotState(
        distance=msg.distance.state,
        effort=Vector2(x=msg.effort.state.x, y=msg.effort.state.y),
        linear_acceleration=Vector3(x=msg.linear_acceleration.state.x, y=msg.linear_acceleration.state.y, z=msg.linear_acceleration.state.z),
        angular_velocity=Vector3(x=msg.angular_velocity.state.x, y=msg.angular_velocity.state.y, z=msg.angular_velocity.state.z),
        magnetic_field=Vector3(x=msg.magnetic_field.state.x, y=msg.magnetic_field.state.y, z=msg.magnetic_field.state.z),
        light_left=msg.light_left.state,
        light_right=msg.light_right.state,
        current_left=msg.current_left.state,
        bus_voltage_left=msg.bus_voltage_left.state,
        power_left=msg.power_left.state,
        current_right=msg.current_right.state,
        bus_voltage_right=msg.bus_voltage_right.state,
        power_right=msg.power_right.state,
        current_supply=msg.current_supply.state,
        bus_voltage_supply=msg.bus_voltage_supply.state,
        power_supply=msg.power_supply.state,
        stamps=stamps
    )

def encode_control(ctrl: RobotControl) -> bytes:
    msg = pb2.Control()
    msg.effort.state.x = ctrl.effort.x
    msg.effort.state.y = ctrl.effort.y
    return msg.SerializeToString()

sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except AttributeError:
    pass
sock_recv.bind(('0.0.0.0', UDP_STATE_PORT))
sock_recv.setblocking(False)

sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

async def perform_discovery_sweep():
    global udp_target_ip, UDP_CONTROL_PORT
    await _broadcast_json({'type': 'log', 'data': 'Starting robot discovery sweep...'})
    interfaces = psutil.net_if_addrs()
    subnets = []
    
    for iface_name, addrs in interfaces.items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                ip = addr.address
                netmask = addr.netmask
                if netmask:
                    try:
                        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                        subnets.append(network)
                    except Exception:
                        pass
    
    # Sort by size
    subnets.sort(key=lambda n: n.num_addresses)
    
    sock_discover = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_discover.setblocking(False)
    sock_discover.bind(('0.0.0.0', 0))
    
    req = pb2.Bonjour()
    req.hmi_port = UDP_STATE_PORT
    req.claim = False
    req.release = False
    req_data = req.SerializeToString()
    
    discovered_robots = {}

    def drain_socket():
        max_reads = 500
        while max_reads > 0:
            max_reads -= 1
            try:
                data, addr = sock_discover.recvfrom(2048)
                resp = pb2.BonjourResponse()
                resp.ParseFromString(data)
                
                info = {
                    'serial': resp.serial,
                    'human_name': resp.human_name,
                    'firmware_version': resp.firmware_version,
                    'ip': addr[0],
                    'port': resp.control_port,
                    'is_claimed': resp.is_claimed,
                    'claimed_by_ip': resp.claimed_by_ip
                }
                key = f"{resp.serial}_{addr[0]}"
                discovered_robots[key] = info
            except BlockingIOError:
                break
            except Exception:
                continue

    for network in subnets:
        is_loop = network.network_address.is_loopback
        if is_loop:
            try:
                sock_discover.sendto(req_data, ("127.0.0.1", 30012))
            except Exception:
                pass
                
    await asyncio.sleep(0.15)
    drain_socket()
    
    for network in subnets:
        is_loop = network.network_address.is_loopback
        if is_loop:
            continue
            
        if network.num_addresses > 65536:
            await _broadcast_json({'type': 'log', 'data': f'Sweeping large network {network}...'})
        count = 0
        
        hosts = network.hosts() if network.prefixlen < 32 else [network.network_address]
            
        for ip in hosts:
            try:
                sock_discover.sendto(req_data, (str(ip), 30012))
            except Exception:
                pass
            count += 1
            if count % 1000 == 0:
                await asyncio.sleep(0) # yield control
                
    await _broadcast_json({'type': 'log', 'data': 'Sweep packets sent. Waiting for responses...'})
    await asyncio.sleep(0.8)
    drain_socket()
    
    if discovered_robots:
        await _broadcast_json({'type': 'log', 'data': f"Discovery sweep finished. Found {len(discovered_robots)} robots."})
        await _broadcast_json({'type': 'robots_discovered', 'robots': list(discovered_robots.values())})
    else:
        await _broadcast_json({'type': 'log', 'data': 'Discovery sweep finished. No robots found.'})
        
    sock_discover.close()

async def udp_loop():
    global current_user_code, current_user_callable
    while True:
        try:
            data, addr = sock_recv.recvfrom(2048)
            state = decode_state(data)
            
            state_dict = {
                'type': 'state',
                'data': {
                    'distance': state.distance,
                    'effort': {'x': state.effort.x, 'y': state.effort.y},
                    'accel': {'x': state.linear_acceleration.x, 'y': state.linear_acceleration.y, 'z': state.linear_acceleration.z},
                    'gyro': {'x': state.angular_velocity.x, 'y': state.angular_velocity.y, 'z': state.angular_velocity.z},
                    'mag': {'x': state.magnetic_field.x, 'y': state.magnetic_field.y, 'z': state.magnetic_field.z},
                    'light_left': state.light_left,
                    'light_right': state.light_right,
                    'current_left': state.current_left,
                    'bus_voltage_left': state.bus_voltage_left,
                    'power_left': state.power_left,
                    'current_right': state.current_right,
                    'bus_voltage_right': state.bus_voltage_right,
                    'power_right': state.power_right,
                    'current_supply': state.current_supply,
                    'bus_voltage_supply': state.bus_voltage_supply,
                    'power_supply': state.power_supply,
                },
                'stamps': state.stamps
            }
            await _broadcast_json(state_dict)

            if current_user_callable:
                try:
                    blank_ctrl = RobotControl(effort=Vector2(0, 0))
                    stdio_buffer = io.StringIO()
                    with contextlib.redirect_stdout(stdio_buffer), contextlib.redirect_stderr(stdio_buffer):
                        raw_result = current_user_callable(state, blank_ctrl)

                    printed = stdio_buffer.getvalue().strip()
                    if printed:
                        for line in printed.splitlines()[-40:]:
                            await _broadcast_json({'type': 'log', 'data': f'[user] {line}'})

                    normalized_ctrl = _normalize_control(raw_result)
                    out_data = encode_control(normalized_ctrl)
                    sock_send.sendto(out_data, (udp_target_ip, UDP_CONTROL_PORT))
                except Exception as e:
                    current_user_code = None
                    current_user_callable = None
                    err_text = traceback.format_exc()
                    await _broadcast_json({'type': 'log', 'data': f"Runtime Error:\n{err_text}"})
                    await _set_runtime_active(False)
                    
        except BlockingIOError:
            await asyncio.sleep(0.01)
        except Exception as e:
            await asyncio.sleep(0.01)

@app.on_event('startup')
async def startup_event():
    asyncio.create_task(udp_loop())
    asyncio.create_task(perform_discovery_sweep())

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    global current_user_code, current_user_callable, udp_target_ip, scripts_dir
    global current_user_code, current_user_callable, udp_target_ip, UDP_CONTROL_PORT, scripts_dir
    await _send_json(websocket, {'type': 'runtime_status', 'active': current_user_callable is not None})
    await _send_json(websocket, {'type': 'scripts_config', 'path': str(_resolve_scripts_dir())})
    await _send_json(websocket, {'type': 'scripts_list', 'scripts': _list_scripts()})
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            print(f"WS Recv: {msg.get('type')}")
            
            if msg.get('type') == 'validate':
                code = msg.get('code', '')
                try:
                    _build_user_callable(code)
                    await _send_json(websocket, {'type': 'validation_result', 'ok': True, 'message': 'Validation successful.'})
                except Exception as e:
                    await _send_json(websocket, {'type': 'validation_result', 'ok': False, 'message': f'Validation error: {e}'})
            
            elif msg.get('type') == 'run':
                code = msg.get('code', '')
                try:
                    user_callable = _build_user_callable(code)
                    current_user_code = code
                    current_user_callable = user_callable
                    await _send_json(websocket, {'type': 'run_result', 'ok': True, 'message': 'Running.'})
                    await _set_runtime_active(True)
                except Exception as e:
                    await _send_json(websocket, {'type': 'run_result', 'ok': False, 'message': f'Run error: {e}'})
                    
            elif msg.get('type') == 'stop':
                current_user_code = None
                current_user_callable = None
                await _send_json(websocket, {'type': 'log', 'data': 'Stopped user script.'})
                await _set_runtime_active(False)

            elif msg.get('type') == 'control':
                effort = msg.get('effort', {}) or {}
                try:
                    ctrl = RobotControl(
                        effort=Vector2(
                            x=float(effort.get('x', 0.0)),
                            y=float(effort.get('y', 0.0)),
                        )
                    )
                    out_data = encode_control(ctrl)
                    sock_send.sendto(out_data, (udp_target_ip, UDP_CONTROL_PORT))
                except Exception as e:
                    await _send_json(websocket, {'type': 'log', 'data': f'Control send error: {e}'})

            elif msg.get('type') == 'set_control_target_ip':
                new_ip = (msg.get('ip', '') or '').strip()
                if not new_ip:
                    await _send_json(websocket, {'type': 'log', 'data': 'Control target IP update error: empty IP'})
                else:
                    udp_target_ip = new_ip
                    await _send_json(websocket, {'type': 'log', 'data': f'Control target IP set to {udp_target_ip}:{UDP_CONTROL_PORT}'})

            elif msg.get('type') == 'set_scripts_path':
                new_path = (msg.get('path', '') or '').strip()
                try:
                    if not new_path:
                        raise ValueError('Scripts path cannot be empty')
                    scripts_dir = _resolve_scripts_dir(new_path)
                    await _send_json(websocket, {'type': 'scripts_config', 'path': str(scripts_dir)})
                    await _send_json(websocket, {'type': 'scripts_list', 'scripts': _list_scripts()})
                    await _send_json(websocket, {'type': 'log', 'data': f'Scripts path set to {scripts_dir}'})
                except Exception as e:
                    await _send_json(websocket, {'type': 'log', 'data': f'Scripts path update error: {e}'})

            elif msg.get('type') == 'list_scripts':
                await _send_json(websocket, {'type': 'scripts_list', 'scripts': _list_scripts()})

            elif msg.get('type') == 'save_script':
                try:
                    code = msg.get('code', '')
                    if 'path' in msg:
                        file_path = Path(msg['path'])
                        file_path.write_text(code, encoding='utf-8')
                        script_name = file_path.name
                    else:
                        script_name = _write_script(msg.get('name', ''), code)
                    await _send_json(websocket, {'type': 'script_saved', 'name': script_name})
                    await _send_json(websocket, {'type': 'log', 'data': f'Script saved: {script_name}'})
                except Exception as e:
                    await _send_json(websocket, {'type': 'log', 'data': f'Script save error: {e}'})

            elif msg.get('type') == 'load_script':
                try:
                    if 'path' in msg:
                        file_path = Path(msg['path'])
                        script_code = file_path.read_text(encoding='utf-8')
                        script_name = file_path.name
                    else:
                        script_name, script_code = _read_script(msg.get('name', ''))
                    await _send_json(websocket, {'type': 'script_loaded', 'name': script_name, 'code': script_code})
                    await _send_json(websocket, {'type': 'log', 'data': f'Script loaded: {script_name}'})
                except Exception as e:
                    await _send_json(websocket, {'type': 'log', 'data': f'Script load error: {e}'})

            elif msg.get('type') == 'scan_robots':
                asyncio.create_task(perform_discovery_sweep())

            elif msg.get('type') == 'claim_robot':
                ip = msg.get('ip')
                port = msg.get('port')
                print(f"WS claim_robot: ip={ip} port={port}")
                
                if udp_target_ip:
                    try:
                        rel_req = pb2.Bonjour()
                        rel_req.hmi_port = UDP_STATE_PORT
                        rel_req.release = True
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rel_sock:
                            rel_sock.bind(("0.0.0.0", 0))
                            rel_sock.settimeout(0.5)
                            rel_sock.sendto(rel_req.SerializeToString(), (udp_target_ip, 30012))
                            try:
                                rel_sock.recvfrom(2048)
                                await _broadcast_json({'type': 'log', 'data': f"Release confirmed by {udp_target_ip}"})
                            except TimeoutError:
                                await _broadcast_json({'type': 'log', 'data': f"Release sent to {udp_target_ip} but timed out"})
                    except Exception as e:
                        await _broadcast_json({'type': 'log', 'data': f"Error releasing {udp_target_ip}: {e}"})
                        
                udp_target_ip = ip
                UDP_CONTROL_PORT = port
                
                try:
                    claim_req = pb2.Bonjour()
                    claim_req.hmi_port = UDP_STATE_PORT
                    claim_req.claim = True
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as claim_sock:
                        claim_sock.bind(("0.0.0.0", 0))
                        claim_sock.settimeout(0.5)
                        claim_sock.sendto(claim_req.SerializeToString(), (udp_target_ip, 30012))
                        try:
                            claim_sock.recvfrom(2048)
                            await _broadcast_json({'type': 'log', 'data': f"Claim confirmed by {udp_target_ip}:30012"})
                        except TimeoutError:
                            await _broadcast_json({'type': 'log', 'data': f"Claim sent to {udp_target_ip} but timed out"})
                except Exception as e:
                    await _broadcast_json({'type': 'log', 'data': f"Error claiming {udp_target_ip}: {e}"})
                    
            elif msg.get('type') == 'release_robot':
                print(f"WS release_robot")
                if udp_target_ip:
                    try:
                        rel_req = pb2.Bonjour()
                        rel_req.hmi_port = UDP_STATE_PORT
                        rel_req.release = True
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rel_sock:
                            rel_sock.bind(("0.0.0.0", 0))
                            rel_sock.settimeout(0.5)
                            rel_sock.sendto(rel_req.SerializeToString(), (udp_target_ip, 30012))
                            try:
                                rel_sock.recvfrom(2048)
                                await _broadcast_json({'type': 'log', 'data': f"Release confirmed by {udp_target_ip}"})
                            except TimeoutError:
                                await _broadcast_json({'type': 'log', 'data': f"Release sent to {udp_target_ip} but timed out"})
                    except Exception as e:
                        await _broadcast_json({'type': 'log', 'data': f"Error releasing {udp_target_ip}: {e}"})
                udp_target_ip = None
                await _broadcast_json({'type': 'robot_released'})

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

if __name__ == '__main__':
    import uvicorn
    import os
    port = int(os.environ.get('KABOT_BACKEND_PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)

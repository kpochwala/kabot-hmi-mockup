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
from models import RobotState, RobotControl, Vector2, Vector3, Stamps
from smpclient import SMPClient
from smpclient.transport.udp import SMPUDPTransport
from smpclient.requests.image_management import ImageStatesRead

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

UDP_STATE_PORT = 30011
UDP_CONTROL_PORT = 30010

udp_target_ip = None
last_state_time = 0.0
robot_connection_status = 'disconnected'

DEFAULT_SCRIPTS_DIR = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'kabot-hmi' / 'scripts'
scripts_dir = DEFAULT_SCRIPTS_DIR

current_user_code = None
current_user_callable = None
active_connections = []


def verify_script(code_text: str):
    return ""

def _build_user_callable(code: str):
    compiled = compile(code, '<user_code>', 'exec')
    local_env = {
        'RobotState': RobotState,
        'RobotControl': RobotControl,
        'Vector2': Vector2,
        'Vector3': Vector3,
        'Stamps': Stamps,
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


ws_lock = None

async def get_ws_lock():
    global ws_lock
    if ws_lock is None:
        ws_lock = asyncio.Lock()
    return ws_lock

async def _send_json(conn: WebSocket, payload: dict):
    lock = await get_ws_lock()
    async with lock:
        await conn.send_text(json.dumps(payload))



def format_log(source: str, msg: str) -> str:
    prefix = f"[{source}] "
    lines = str(msg).splitlines()
    if not lines:
        return prefix
    out = prefix + lines[0]
    indent = " " * len(prefix)
    for line in lines[1:]:
        out += f"\n{indent}{line}"
    return out

async def _broadcast_log(source: str, msg: str):
    await _broadcast_json({'type': 'log', 'data': format_log(source, msg)})

async def _send_log(conn, source: str, msg: str):
    await _send_json(conn, {'type': 'log', 'data': format_log(source, msg)})

async def _broadcast_json(payload: dict):

    stale = []
    data = json.dumps(payload)
    lock = await get_ws_lock()
    async with lock:
        for conn in active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                stale.append(conn)
    for conn in stale:
        if conn in active_connections:
            active_connections.remove(conn)
_firmware_fetch_locks: dict[str, asyncio.Lock] = {}
_discovery_lock = asyncio.Lock()
smp_in_progress = False

import smp_fetcher
import smp_action
import smp_uploader

def get_firmware_fetch_lock(ip: str) -> asyncio.Lock:
    if ip not in _firmware_fetch_locks:
        _firmware_fetch_locks[ip] = asyncio.Lock()
    return _firmware_fetch_locks[ip]

async def fetch_firmware_status(ip: str):
    global udp_target_ip, smp_in_progress
    lock = get_firmware_fetch_lock(ip)
        
    if lock.locked():
        await _broadcast_log('HMI', f"Firmware fetch already in progress for {ip}, skipping")
        return

    async with lock:
        async with _discovery_lock:
            # Check if this robot is currently claimed
            was_claimed = (udp_target_ip == ip)
            if was_claimed:
                await _broadcast_log('HMI', f"Temporarily releasing {ip} to safely fetch firmware via SMP")
                try:
                    rel_req = pb2.Bonjour()
                    rel_req.hmi_port = UDP_STATE_PORT
                    rel_req.release = True
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rel_sock:
                        rel_sock.bind(("0.0.0.0", 0))
                        rel_sock.settimeout(0.5)
                        rel_sock.sendto(rel_req.SerializeToString(), (ip, 30012))
                        try:
                            rel_sock.recvfrom(2048)
                        except TimeoutError:
                            pass
                except Exception as e:
                    await _broadcast_log('HMI', f"Error during temp release: {e}")
                
                # Pause background pings immediately
                udp_target_ip = None
                
            # Block ALL other background tasks (discovery, pings, loop)
            smp_in_progress = True
            
            # Wait a long time for the robot's network stack to completely clear out old telemetry
            await asyncio.sleep(2.0)

            await _broadcast_log('HMI', f"Fetching firmware status from {ip}")
            try:
                result = await smp_fetcher.fetch_firmware_status(ip)
                if "data" in result:
                    await _broadcast_json({'type': 'firmware_status', 'ip': ip, 'data': result["data"]})
                    await _broadcast_log('HMI', f"Firmware status fetched successfully from {ip}")
                else:
                    await _broadcast_log('HMI', f"Firmware status fetch successfully completed for {ip}")
            except Exception as e:
                err_str = repr(e)
                if len(err_str) > 200:
                    err_str = err_str[:200] + '...'
                await _broadcast_log('HMI', f"SMP fetch failed for {ip}: {err_str}")
                await _broadcast_json({'type': 'firmware_status_error', 'ip': ip, 'message': 'Status fetch failed'})
            finally:
                # Re-enable background tasks
                smp_in_progress = False
                
                # Reclaim if we temporarily released it
                if was_claimed:
                    await asyncio.sleep(0.5)
                    await _broadcast_log('HMI', f"Re-claiming {ip} after firmware fetch")
                    udp_target_ip = ip
                    try:
                        claim_req = pb2.Bonjour()
                        claim_req.hmi_port = UDP_STATE_PORT
                        claim_req.claim = True
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as claim_sock:
                            claim_sock.bind(("0.0.0.0", 0))
                            claim_sock.settimeout(0.5)
                            claim_sock.sendto(claim_req.SerializeToString(), (ip, 30012))
                    except Exception as e:
                        await _broadcast_log('HMI', f"Error during re-claim: {e}")

async def boot_firmware_slot(ip: str, slot_hash: str):
    global smp_in_progress, udp_target_ip
    
    was_claimed = False
    lock = get_firmware_fetch_lock(ip)
    async with lock:
        async with _discovery_lock:
            was_claimed = (udp_target_ip == ip)
            smp_in_progress = True
            try:
                await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': 'Setting slot to pending'})
                await smp_action.run_smp_action(ip, "pending", slot_hash)
                
                await asyncio.sleep(0.5)
                
                await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': 'Fetching status before reboot'})
                try:
                    result = await smp_fetcher.fetch_firmware_status(ip)
                    if "data" in result:
                        await _broadcast_json({'type': 'firmware_status', 'ip': ip, 'data': result["data"]})
                except Exception as fetch_err:
                    await _broadcast_log('HMI', f"Failed to fetch status before reboot: {fetch_err}")
                
                await asyncio.sleep(0.5)
                
                await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': 'Rebooting robot...'})
                try:
                    await smp_action.run_smp_action(ip, "reset", "none")
                except Exception:
                    pass # might fail if robot drops immediately
                
                await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': 'Waiting for boot...'})
            except Exception as e:
                await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': ''})
                await _broadcast_log('HMI', f"Error booting slot: {e}")
            finally:
                smp_in_progress = False

    # Try to fetch status up to 10 times (30 seconds)
    import json
    import sys
    import subprocess
    for i in range(10):
        await asyncio.sleep(3.0)
        try:
            await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': f'Trying to fetch slot status... ({i+1}/10)'})
            proc_fetch = await asyncio.create_subprocess_exec(
                sys.executable, "smp_fetcher.py", ip,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout_fetch, _ = await proc_fetch.communicate()
            if proc_fetch.returncode == 0:
                result = json.loads(stdout_fetch.decode().strip())
                if "data" in result:
                    await _broadcast_json({'type': 'firmware_status', 'ip': ip, 'data': result["data"]})
                    await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': ''})
                    await _broadcast_log('HMI', f"Robot {ip} is back online!")
                    if was_claimed:
                        udp_target_ip = ip
                    break
        except Exception:
            pass
    else:
        # Loop finished without breaking
        await _broadcast_json({'type': 'firmware_boot_phase', 'ip': ip, 'hash': slot_hash, 'phase': ''})

async def confirm_firmware_slot(ip: str, slot_hash: str):
    global smp_in_progress
    lock = get_firmware_fetch_lock(ip)
    async with lock:
        async with _discovery_lock:
            smp_in_progress = True
            try:
                await _broadcast_log('HMI', f"Confirming firmware slot on {ip}...")
                await smp_action.run_smp_action(ip, "confirm", slot_hash)
                await _broadcast_log('HMI', f"Slot confirmed on {ip}.")
            except Exception as e:
                await _broadcast_log('HMI', f"Error confirming slot: {e}")
            finally:
                smp_in_progress = False
    
    # Refresh status after releasing locks
    asyncio.create_task(fetch_firmware_status(ip))

async def fetch_github_releases():
    import urllib.request
    import urllib.error
    import json
    
    url = "https://api.github.com/repos/kabot-io/kabot-zephyr/releases"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'kabot-hmi-mockup'})
        loop = asyncio.get_event_loop()
        def _fetch():
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        releases_data = await loop.run_in_executor(None, _fetch)
        
        valid_releases = []
        for release in releases_data:
            assets = release.get('assets', [])
            for asset in assets:
                if asset.get('name', '').endswith('.signed.bin'):
                    valid_releases.append({
                        'name': release.get('name') or release.get('tag_name'),
                        'tag': release.get('tag_name'),
                        'url': asset.get('browser_download_url'),
                        'published_at': release.get('published_at')
                    })
                    break
                    
        await _broadcast_json({'type': 'github_releases', 'data': valid_releases})
    except urllib.error.URLError as e:
        await _broadcast_json({'type': 'github_releases', 'error': f"Failed to fetch releases: {e.reason}"})
    except Exception as e:
        await _broadcast_json({'type': 'github_releases', 'error': f"Failed to fetch releases: {e}"})

async def flash_firmware(ip: str, fw_url: str = None):
    global udp_target_ip, smp_in_progress
    lock = get_firmware_fetch_lock(ip)
        
    if lock.locked():
        await _broadcast_log('HMI', f"Firmware operation already in progress for {ip}, skipping")
        return

    async with lock:
        async with _discovery_lock:
            was_claimed = (udp_target_ip == ip)
            if was_claimed:
                await _broadcast_log('HMI', f"Temporarily releasing {ip} to safely flash firmware via SMP")
                try:
                    rel_req = pb2.Bonjour()
                    rel_req.hmi_port = UDP_STATE_PORT
                    rel_req.release = True
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rel_sock:
                        rel_sock.bind(("0.0.0.0", 0))
                        rel_sock.settimeout(0.5)
                        rel_sock.sendto(rel_req.SerializeToString(), (ip, 30012))
                        try:
                            rel_sock.recvfrom(2048)
                        except TimeoutError:
                            pass
                except Exception as e:
                    await _broadcast_log('HMI', f"Error during temp release: {e}")
                
                udp_target_ip = None
                
            smp_in_progress = True
            
            await asyncio.sleep(2.0)

            try:
                # Pre-flight check: fetch firmware status
                await _broadcast_json({'type': 'firmware_flash_phase', 'ip': ip, 'phase': 'Updating firmware status'})
                await _broadcast_log('HMI', f"Fetching firmware status from {ip} before flashing...")
                try:
                    result_fetch = await smp_fetcher.fetch_firmware_status(ip)
                    if "data" in result_fetch:
                        await _broadcast_json({'type': 'firmware_status', 'ip': ip, 'data': result_fetch["data"]})
                    else:
                        raise RuntimeError("Status fetch failed: no data")
                except Exception as fetch_err:
                    raise RuntimeError(f"Status fetch failed: {fetch_err}")

                # Give Zephyr UDP stack a moment to clean up before opening a new socket
                await asyncio.sleep(0.5)

                await _broadcast_json({'type': 'firmware_flash_phase', 'ip': ip, 'phase': 'Uploading firmware'})
                await _broadcast_log('HMI', f"Flashing firmware to {ip} via isolated subprocess")
                
                if fw_url:
                    await _broadcast_json({'type': 'firmware_flash_phase', 'ip': ip, 'phase': 'Downloading firmware'})
                    await _broadcast_log('HMI', f"Downloading firmware from {fw_url}...")
                    
                    import urllib.request
                    import tempfile
                    import shutil
                    def _download():
                        req = urllib.request.Request(fw_url, headers={'User-Agent': 'kabot-hmi-mockup'})
                        with urllib.request.urlopen(req) as response:
                            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".signed.bin")
                            shutil.copyfileobj(response, tmp_file)
                            tmp_file.close()
                            return tmp_file.name
                            
                    try:
                        loop = asyncio.get_event_loop()
                        fw_path = await loop.run_in_executor(None, _download)
                        await _broadcast_log('HMI', f"Downloaded firmware to temporary file for flashing")
                        # Re-broadcast phase back to Uploading firmware
                        await _broadcast_json({'type': 'firmware_flash_phase', 'ip': ip, 'phase': 'Uploading firmware'})
                    except Exception as e:
                        raise RuntimeError(f"Failed to download firmware: {e}")
                else:
                    raise RuntimeError("No firmware URL provided for flashing")
                
                async def progress_cb(prog: float):
                    await _broadcast_json({
                        'type': 'firmware_flash_progress',
                        'ip': ip,
                        'progress': prog
                    })
                
                await smp_uploader.upload_firmware(ip, fw_path, progress_cb)
                    
                await asyncio.sleep(0.5)
                await _broadcast_json({'type': 'firmware_flash_phase', 'ip': ip, 'phase': 'Updating firmware status'})
                
                # Post-flight fetch to get updated slots
                try:
                    result_fetch_post = await smp_fetcher.fetch_firmware_status(ip)
                    if "data" in result_fetch_post:
                        await _broadcast_json({'type': 'firmware_status', 'ip': ip, 'data': result_fetch_post["data"]})
                except Exception:
                    pass
                    
                await _broadcast_log('HMI', f"Firmware flash completed successfully for {ip}")
                await _broadcast_json({'type': 'firmware_flash_success', 'ip': ip})
            except Exception as e:
                err_str = repr(e)
                if len(err_str) > 200:
                    err_str = err_str[:200] + '...'
                await _broadcast_log('HMI', f"SMP flash failed for {ip}: {err_str}")
                
                # Forward the actual exception message so it shows in the UI
                msg = str(e)
                if len(msg) > 100:
                    msg = msg[:97] + '...'
                await _broadcast_json({'type': 'firmware_flash_error', 'ip': ip, 'message': msg})
            finally:
                smp_in_progress = False
                
                if was_claimed:
                    await asyncio.sleep(0.5)
                    await _broadcast_log('HMI', f"Re-claiming {ip} after firmware flash")
                    udp_target_ip = ip
                    try:
                        claim_req = pb2.Bonjour()
                        claim_req.hmi_port = UDP_STATE_PORT
                        claim_req.claim = True
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as claim_sock:
                            claim_sock.bind(("0.0.0.0", 0))
                            claim_sock.settimeout(0.5)
                            claim_sock.sendto(claim_req.SerializeToString(), (ip, 30012))
                    except Exception as e:
                        await _broadcast_log('HMI', f"Error during re-claim: {e}")
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
    
    stamps = Stamps(
        state=msg.header.stamp,
        distance=msg.distance.header.stamp,
        effort=msg.effort.header.stamp,
        accel=msg.linear_acceleration.header.stamp,
        gyro=msg.angular_velocity.header.stamp,
        mag=msg.magnetic_field.header.stamp,
        light_left=msg.light_left.header.stamp,
        light_right=msg.light_right.header.stamp,
        current_left=msg.current_left.header.stamp,
        bus_voltage_left=msg.bus_voltage_left.header.stamp,
        power_left=msg.power_left.header.stamp,
        current_right=msg.current_right.header.stamp,
        bus_voltage_right=msg.bus_voltage_right.header.stamp,
        power_right=msg.power_right.header.stamp,
        current_supply=msg.current_supply.header.stamp,
        bus_voltage_supply=msg.bus_voltage_supply.header.stamp,
        power_supply=msg.power_supply.header.stamp,
    )
    
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

backend_port_conflict = None

sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock_recv.bind(('0.0.0.0', UDP_STATE_PORT))
except OSError:
    backend_port_conflict = UDP_STATE_PORT
sock_recv.setblocking(False)

sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

async def perform_discovery_sweep():
    global active_connections, _discovery_lock, _firmware_fetch_locks, smp_in_progress
    if smp_in_progress:
        return
        
    if _discovery_lock.locked() or any(lock.locked() for lock in _firmware_fetch_locks.values()):
        await _broadcast_log('HMI', 'Skipping robot discovery sweep because firmware fetch is in progress...')
        return
        
    async with _discovery_lock:
        await _broadcast_log('HMI', 'Starting robot discovery sweep...')
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
                            # Exclude loopback and massive subnets (e.g. /8) which take hours to sweep
                            if not network.is_loopback and network.num_addresses <= 65536:
                                subnets.append(network)
                        except ValueError:
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
                        'claimed_by_ip': resp.claimed_by_ip,
                        'is_claimed_by_us': resp.is_claimed and (resp.claimed_by_ip in local_ips)
                    }
                    key = f"{resp.serial}_{addr[0]}"
                    discovered_robots[key] = info
                except BlockingIOError:
                    break
                except Exception:
                    continue

        last_sweep_time = getattr(perform_discovery_sweep, 'last_sweep_time', 0)
        current_time = asyncio.get_event_loop().time()
        if current_time - last_sweep_time < 5.0:
            await _broadcast_log('HMI', 'Discovery sweep throttled (too soon).')
            await _broadcast_json({'type': 'robots_discovered', 'robots': list(discovered_robots.values())})
            return
        perform_discovery_sweep.last_sweep_time = current_time

        await _broadcast_log('HMI', 'Starting fast broadcast discovery sweep...')
        
        # Broadcast scan
        sock_discover.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock_discover.sendto(req_data, ('255.255.255.255', 30012))
        except Exception:
            pass
            
        await asyncio.sleep(0.5)
        drain_socket()
        
        if discovered_robots:
            await _broadcast_log('HMI', f"Broadcast sweep finished. Found {len(discovered_robots)} robots.")
            await _broadcast_json({'type': 'robots_discovered', 'robots': list(discovered_robots.values())})
            sock_discover.close()
            return

        # If no robots found by broadcast, proceed with full sweep
        await _broadcast_log('HMI', 'No robots found via broadcast. Proceeding with full subnet sweep...')
        for sweep_idx in range(1):
            for subnet in subnets:
                for ip in subnet.hosts():
                    # Abort sweep if firmware fetch is requested
                    if any(lock.locked() for lock in _firmware_fetch_locks.values()):
                        await _broadcast_log('HMI', 'Aborting full subnet sweep due to firmware fetch request.')
                        sock_discover.close()
                        return
                        
                    try:
                        sock_discover.sendto(req_data, (str(ip), 30012))
                        await asyncio.sleep(0.001)  # tiny delay to not hog CPU/buffer
                    except Exception:
                        pass
                drain_socket()
                    
        await _broadcast_log('HMI', 'Sweep packets sent. Waiting for late responses...')
        await asyncio.sleep(0.8)
        drain_socket()
        
        if discovered_robots:
            await _broadcast_log('HMI', f"Discovery sweep finished. Found {len(discovered_robots)} robots.")
            await _broadcast_json({'type': 'robots_discovered', 'robots': list(discovered_robots.values())})
        else:
            await _broadcast_log('HMI', 'Discovery sweep finished. No robots found.')
            await _broadcast_json({'type': 'robots_discovered', 'robots': []})
            
        sock_discover.close()

async def udp_loop():
    global current_user_code, current_user_callable, backend_port_conflict, smp_in_progress
    while True:
        if backend_port_conflict or smp_in_progress:
            await asyncio.sleep(1)
            continue
        try:
            data, addr = sock_recv.recvfrom(2048)
            if not udp_target_ip or addr[0] != udp_target_ip:
                continue
                
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
                'stamps': state.stamps.__dict__ if hasattr(state.stamps, '__dict__') else state.stamps
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
                            await _broadcast_log('User Script', f'{line}')

                    normalized_ctrl = _normalize_control(raw_result)
                    out_data = encode_control(normalized_ctrl)
                    sock_send.sendto(out_data, (udp_target_ip, UDP_CONTROL_PORT))
                except Exception as e:
                    current_user_code = None
                    current_user_callable = None
                    err_text = traceback.format_exc()
                    await _broadcast_log('User Script', f"Runtime Error:\n{err_text}")
                    await _set_runtime_active(False)
                    
        except BlockingIOError:
            await asyncio.sleep(0.01)
        except Exception as e:
            print(f"udp_loop exception: {e}")
            traceback.print_exc()
            await asyncio.sleep(0.01)

original_ppid = os.getppid()

async def continuous_ping():
    global udp_target_ip, UDP_STATE_PORT, smp_in_progress
    fail_count = 0
    last_ping_status = 'disconnected'
    while True:
        await asyncio.sleep(1)
        if not udp_target_ip or smp_in_progress:
            fail_count = 0
            last_ping_status = 'disconnected'
            continue
            
        req = pb2.Bonjour()
        req.hmi_port = UDP_STATE_PORT
        req.claim = False
        req.release = False
        req_data = req.SerializeToString()
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as ping_sock:
                ping_sock.bind(("0.0.0.0", 0))
                ping_sock.settimeout(0.5)
                ping_sock.sendto(req_data, (udp_target_ip, 30012))
                ping_sock.recvfrom(2048)
                fail_count = 0
                if last_ping_status != 'connected':
                    await _broadcast_json({'type': 'robot_connection_status', 'status': 'connected'})
                    last_ping_status = 'connected'
        except Exception:
            fail_count += 1
            if fail_count >= 10:
                print(f"Ping failed {fail_count} times. Disconnecting.")
                await _broadcast_json({'type': 'robot_disconnected', 'ip': udp_target_ip})
                udp_target_ip = None
                fail_count = 0
                last_ping_status = 'disconnected'
                global current_user_callable
                if current_user_callable:
                    current_user_callable = None
                    await _set_runtime_active(False)
                    await _broadcast_log('HMI', 'Robot disconnected. Stopped user script.')
            elif last_ping_status != 'warning':
                await _broadcast_json({'type': 'robot_connection_status', 'status': 'warning'})
                last_ping_status = 'warning'

async def check_parent_alive():
    while True:
        if os.getppid() != original_ppid:
            print("Parent process died or reparented. Exiting.")
            os._exit(0)
        await asyncio.sleep(1)

@app.on_event('startup')
async def startup_event():
    asyncio.create_task(udp_loop())
    asyncio.create_task(perform_discovery_sweep())
    asyncio.create_task(check_parent_alive())
    asyncio.create_task(continuous_ping())

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if backend_port_conflict:
        await websocket.send_json({'type': 'port_conflict', 'port': backend_port_conflict})
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
            
            if msg.get('type') == 'run':
                code = msg.get('code', '')
                import traceback
                try:
                    user_callable = _build_user_callable(code)
                    current_user_code = code
                    await _send_json(websocket, {'type': 'run_result', 'ok': True, 'message': 'Running.'})
                    await _set_runtime_active(True)
                    current_user_callable = user_callable
                except SyntaxError as e:
                    err_lines = traceback.format_exception_only(type(e), e)
                    err_str = "".join(err_lines).strip()
                    await _broadcast_log('Script Validation', f"Error parsing script:\n{err_str}")
                    await _send_json(websocket, {'type': 'run_result', 'ok': False, 'message': f'Run error: Syntax Error'})
                    await _set_runtime_active(False)
                except Exception as e:
                    err_text = traceback.format_exc()
                    current_user_code = None
                    current_user_callable = None
                    await _broadcast_log('Script Validation', f"Error parsing script:\n{err_text}")
                    await _send_json(websocket, {'type': 'run_result', 'ok': False, 'message': f'Run error: {e}'})
                    await _set_runtime_active(False)
                    
            elif msg.get('type') == 'stop':
                current_user_code = None
                current_user_callable = None
                await _send_log(websocket, 'User Script', 'Stopped user script.')
                await _set_runtime_active(False)

            elif msg.get('type') == 'verify':
                code_text = msg.get('code', '')
                import traceback
                try:
                    warnings = verify_script(code_text)
                    if warnings:
                        await _send_log(websocket, 'Script Validation', warnings)
                    else:
                        await _send_log(websocket, 'Script Validation', 'Syntax verification passed!')
                except SyntaxError as e:
                    err_lines = traceback.format_exception_only(type(e), e)
                    err_str = "".join(err_lines).strip()
                    await _send_log(websocket, 'Script Validation', f"Error parsing script:\n{err_str}")
                except Exception as e:
                    await _send_log(websocket, 'Script Validation', f"Verification error: {e}")

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
                    await _send_log(websocket, 'HMI', f'Control send error: {e}')

            elif msg.get('type') == 'set_control_target_ip':
                new_ip = (msg.get('ip', '') or '').strip()
                if not new_ip:
                    await _send_log(websocket, 'HMI', 'Control target IP update error: empty IP')
                else:
                    udp_target_ip = new_ip
                    await _send_log(websocket, 'HMI', f'Control target IP set to {udp_target_ip}:{UDP_CONTROL_PORT}')

            elif msg.get('type') == 'set_scripts_path':
                new_path = (msg.get('path', '') or '').strip()
                try:
                    if not new_path:
                        raise ValueError('Scripts path cannot be empty')
                    scripts_dir = _resolve_scripts_dir(new_path)
                    await _send_json(websocket, {'type': 'scripts_config', 'path': str(scripts_dir)})
                    await _send_json(websocket, {'type': 'scripts_list', 'scripts': _list_scripts()})
                    await _send_log(websocket, 'HMI', f'Scripts path set to {scripts_dir}')
                except Exception as e:
                    await _send_log(websocket, 'HMI', f'Scripts path update error: {e}')

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
                    await _send_log(websocket, 'HMI', f'Script saved: {script_name}')
                except Exception as e:
                    await _send_log(websocket, 'HMI', f'Script save error: {e}')

            elif msg.get('type') == 'load_script':
                try:
                    if 'path' in msg:
                        file_path = Path(msg['path'])
                        script_code = file_path.read_text(encoding='utf-8')
                        script_name = file_path.name
                    else:
                        script_name, script_code = _read_script(msg.get('name', ''))
                    await _send_json(websocket, {'type': 'script_loaded', 'name': script_name, 'code': script_code})
                    await _send_log(websocket, 'HMI', f'Script loaded: {script_name}')
                except Exception as e:
                    await _send_log(websocket, 'HMI', f'Script load error: {e}')

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
                                await _broadcast_log('HMI', f"Release confirmed by {udp_target_ip}")
                            except TimeoutError:
                                await _broadcast_log('HMI', f"Release sent to {udp_target_ip} but timed out")
                    except Exception as e:
                        await _broadcast_log('HMI', f"Error releasing {udp_target_ip}: {e}")
                        
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
                            await _broadcast_log('HMI', f"Claim confirmed by {udp_target_ip}:30012")
                            await _broadcast_json({'type': 'claim_accepted', 'ip': udp_target_ip})
                        except TimeoutError:
                            await _broadcast_log('HMI', f"Claim sent to {udp_target_ip} but timed out")
                except Exception as e:
                    await _broadcast_log('HMI', f"Error claiming {udp_target_ip}: {e}")
                    udp_target_ip = None
                    UDP_CONTROL_PORT = 30010
            
            elif msg.get('type') == 'refresh_firmware_status':
                target_ip = msg.get('ip') or udp_target_ip
                if target_ip:
                    asyncio.create_task(fetch_firmware_status(target_ip))
                else:
                    await _send_log(websocket, 'HMI', "Cannot refresh firmware status: no IP provided and no robot claimed")

            elif msg.get('type') == 'fetch_github_releases':
                asyncio.create_task(fetch_github_releases())

            elif msg.get('type') == 'boot_slot':
                target_ip = msg.get('ip') or udp_target_ip
                slot_hash = msg.get('hash')
                if target_ip and slot_hash:
                    asyncio.create_task(boot_firmware_slot(target_ip, slot_hash))
                else:
                    await _send_log(websocket, 'HMI', "Cannot boot slot: missing IP or hash")
                    
            elif msg.get('type') == 'confirm_slot':
                target_ip = msg.get('ip') or udp_target_ip
                slot_hash = msg.get('hash')
                if target_ip and slot_hash:
                    asyncio.create_task(confirm_firmware_slot(target_ip, slot_hash))
                else:
                    await _send_log(websocket, 'HMI', "Cannot confirm slot: missing IP or hash")

            elif msg.get('type') == 'flash_firmware':
                target_ip = msg.get('ip') or udp_target_ip
                fw_url = msg.get('url')
                if target_ip:
                    asyncio.create_task(flash_firmware(target_ip, fw_url))
                else:
                    await _send_log(websocket, 'HMI', "Cannot flash firmware: no IP provided")

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
                                await _broadcast_log('HMI', f"Release confirmed by {udp_target_ip}")
                            except TimeoutError:
                                await _broadcast_log('HMI', f"Release sent to {udp_target_ip} but timed out")
                    except Exception as e:
                        await _broadcast_log('HMI', f"Error releasing {udp_target_ip}: {e}")
                old_ip = udp_target_ip
                udp_target_ip = None
                await _broadcast_json({'type': 'robot_released', 'ip': old_ip})

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
        if not active_connections:
            if udp_target_ip:
                try:
                    rel_req = pb2.Bonjour()
                    rel_req.hmi_port = UDP_STATE_PORT
                    rel_req.release = True
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rel_sock:
                        rel_sock.bind(("0.0.0.0", 0))
                        rel_sock.settimeout(0.5)
                        rel_sock.sendto(rel_req.SerializeToString(), (udp_target_ip, 30012))
                except Exception:
                    pass
                udp_target_ip = None

if __name__ == '__main__':
    import uvicorn
    import os
    port = int(os.environ.get('KABOT_BACKEND_PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)

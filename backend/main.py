import asyncio
import socket
import traceback
import json
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
UDP_TARGET_IP = '127.0.0.1'

current_user_code = None
active_connections = []

def decode_state(data: bytes) -> RobotState:
    msg = pb2.State()
    msg.ParseFromString(data)
    
    stamps = {
        'state': msg.header.stamp,
        'distance': msg.distance.header.stamp,
        'effort': msg.effort.header.stamp,
        'accel': msg.linear_acceleration.header.stamp,
        'gyro': msg.angular_velocity.header.stamp,
        'mag': msg.magnetic_field.header.stamp
    }
    
    return RobotState(
        distance=msg.distance.state,
        effort=Vector2(x=msg.effort.state.x, y=msg.effort.state.y),
        linear_acceleration=Vector3(x=msg.linear_acceleration.state.x, y=msg.linear_acceleration.state.y, z=msg.linear_acceleration.state.z),
        angular_velocity=Vector3(x=msg.angular_velocity.state.x, y=msg.angular_velocity.state.y, z=msg.angular_velocity.state.z),
        magnetic_field=Vector3(x=msg.magnetic_field.state.x, y=msg.magnetic_field.state.y, z=msg.magnetic_field.state.z),
        stamps=stamps
    )

def encode_control(ctrl: RobotControl) -> bytes:
    msg = pb2.Control()
    msg.effort.state.x = ctrl.effort.x
    msg.effort.state.y = ctrl.effort.y
    return msg.SerializeToString()

sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_recv.bind(('0.0.0.0', UDP_STATE_PORT))
sock_recv.setblocking(False)

sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

async def udp_loop():
    global current_user_code
    loop = asyncio.get_event_loop()
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
                    'mag': {'x': state.magnetic_field.x, 'y': state.magnetic_field.y, 'z': state.magnetic_field.z}
                },
                'stamps': state.stamps
            }
            for conn in active_connections:
                asyncio.create_task(conn.send_text(json.dumps(state_dict)))

            if current_user_code:
                local_env = {'RobotState': RobotState, 'RobotControl': RobotControl, 'Vector2': Vector2, 'Vector3': Vector3}
                try:
                    exec(current_user_code, local_env)
                    if 'control' in local_env:
                        user_func = local_env['control']
                        blank_ctrl = RobotControl(effort=Vector2(0, 0))
                        result_ctrl = user_func(state, blank_ctrl)
                        if result_ctrl:
                            out_data = encode_control(result_ctrl)
                            sock_send.sendto(out_data, (UDP_TARGET_IP, UDP_CONTROL_PORT))
                except Exception as e:
                    current_user_code = None
                    err_msg = {'type': 'log', 'data': f"Runtime Error: {e}"}
                    for conn in active_connections:
                        asyncio.create_task(conn.send_text(json.dumps(err_msg)))
                    
        except BlockingIOError:
            await asyncio.sleep(0.01)
        except Exception as e:
            await asyncio.sleep(0.01)

@app.on_event('startup')
async def startup_event():
    asyncio.create_task(udp_loop())

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    global current_user_code
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get('type') == 'validate':
                code = msg.get('code', '')
                try:
                    compile(code, '<string>', 'exec')
                    await websocket.send_text(json.dumps({'type': 'log', 'data': 'Validation successful.'}))
                except Exception as e:
                    await websocket.send_text(json.dumps({'type': 'log', 'data': f'Validation error: {e}'}))
            
            elif msg.get('type') == 'run':
                code = msg.get('code', '')
                try:
                    compile(code, '<string>', 'exec')
                    current_user_code = code
                    await websocket.send_text(json.dumps({'type': 'log', 'data': 'Running...'}))
                except Exception as e:
                    await websocket.send_text(json.dumps({'type': 'log', 'data': f'Run error: {e}'}))
                    
            elif msg.get('type') == 'stop':
                current_user_code = None
                await websocket.send_text(json.dumps({'type': 'log', 'data': 'Stopped.'}))

    except WebSocketDisconnect:
        active_connections.remove(websocket)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)

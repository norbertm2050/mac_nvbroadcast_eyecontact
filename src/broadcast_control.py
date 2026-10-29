"""Broadcast 2.3 local MCP client. Remote callers use authenticated SSH, never a LAN listener."""
import base64
import http.client
import json
import os
from contextlib import contextmanager
from pathlib import Path


class BroadcastError(RuntimeError):
    pass


class NoCameraDevices(BroadcastError):
    """Gateway responded, but lost its entire camera enumeration."""
    pass


class BroadcastClient:
    def __init__(self, port=None, timeout=12):
        if port is None:
            path = Path(os.environ['APPDATA']) / 'nvidia-broadcast/gateway.json'
            port = json.loads(base64.b64decode(path.read_text().strip(), validate=True))['port']
        if type(port) is not int or not 18100 <= port <= 18109:
            raise BroadcastError('Invalid Broadcast gateway port')
        self.port, self.timeout = port, timeout
        self.session = None
        self.version = '2024-11-05'
        self.sequence = 0
        self.info = self.request('initialize', {'protocolVersion': self.version,
            'capabilities': {}, 'clientInfo': {'name': 'remote-eye-contact', 'version': '1.2.0'}})
        if self.info.get('serverInfo', {}).get('name') != 'nvidia-broadcast':
            raise BroadcastError('Gateway is not NVIDIA Broadcast')
        self.version = self.info['protocolVersion']
        self.request('notifications/initialized', notification=True)

    def request(self, method, params=None, notification=False):
        self.sequence += 1
        payload = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            payload['params'] = params
        if not notification:
            payload['id'] = self.sequence
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': self.version}
        if self.session:
            headers['Mcp-Session-Id'] = self.session
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            connection.request('POST', '/gateway', json.dumps(payload), headers)
            response = connection.getresponse()
            if response.status not in (200, 202, 204):
                raise BroadcastError(f'Broadcast HTTP {response.status}')
            self.session = response.getheader('Mcp-Session-Id') or self.session
            if notification:
                return None
            if 'text/event-stream' in response.getheader('Content-Type', ''):
                data, size = [], 0
                while True:
                    line = response.readline(1024 * 1024)
                    size += len(line)
                    if size > 1024 * 1024:
                        raise BroadcastError('Oversized MCP response')
                    if not line:
                        raise BroadcastError('MCP stream ended before response')
                    line = line.decode('utf-8').rstrip('\r\n')
                    if line.startswith('data:'):
                        data.append(line[5:].lstrip())
                    if not line and data:
                        result = json.loads('\n'.join(data)); data = []
                        if result.get('id') == payload['id']:
                            break
            else:
                body = response.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise BroadcastError('Oversized MCP response')
                result = json.loads(body)
            if result.get('id') != payload['id']:
                raise BroadcastError('MCP response id mismatch')
            if 'error' in result:
                raise BroadcastError(json.dumps(result['error']))
            return result['result']
        finally:
            connection.close()

    def tools(self):
        return self.request('tools/list')['tools']

    def call(self, name, arguments=None):
        result = self.request('tools/call', {'name': name, 'arguments': arguments or {}})
        data = result.get('structuredContent')
        if data is None:
            text = '\n'.join(x['text'] for x in result.get('content', []) if x.get('type') == 'text')
            try:
                data = json.loads(text)
            except ValueError:
                raise BroadcastError('MCP tool returned no structured result')
        if result.get('isError') or 'error' in data:
            raise BroadcastError(json.dumps(data))
        return data

    def close(self):
        if not self.session:
            return
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            connection.request('DELETE', '/gateway', headers={'Mcp-Session-Id': self.session,
                               'MCP-Protocol-Version': self.version})
            connection.getresponse().close()
        except OSError:
            pass
        finally:
            connection.close()
            self.session = None


def camera_summary(devices, state):
    return {'cameras': [{'name': d['name'], 'active': d.get('active', False),
                         'resolution': d.get('currentResolution'),
                         'availableResolutions': d.get('availableResolutions', [])}
                        for d in devices.get('cameras', [])],
            'enabledCameraEffects': [name for name, effect in state.get('camera', {}).items()
                                     if effect.get('enabled')]}


def prepare_pipeline(client, restore_live=False):
    """Idempotent camera-only setup; never guess device IDs or unsupported modes."""
    tools = {tool['name']: tool for tool in client.tools()}
    needed = {'list_devices', 'get_broadcast_state', 'set_effects', 'set_active_device',
              'get_file_processing_jobs'}
    if not needed.issubset(tools):
        raise BroadcastError('Broadcast gateway lacks required control tools')
    changed = []
    if restore_live:
        result = client.call('set_effects', {'action': 'restore_previous_live'})
        changed.append(result.get('event', 'restore_previous_live'))
    else:
        jobs = client.call('get_file_processing_jobs', {'_version': 1, 'status': 'in_progress'})
        if jobs.get('jobs') or jobs.get('status') == 'in_progress':
            raise BroadcastError('Broadcast is processing files; explicitly restore Live before streaming')
    state = client.call('get_broadcast_state')
    camera = state.get('camera', {})
    allowed = tools['set_effects']['inputSchema']['properties']['effects']['items']['properties']['effectId']['enum']
    if 'eye_contact' not in allowed:
        raise BroadcastError('Eye Contact is unavailable on this Broadcast/GPU')
    unwanted = [{'effectId': name, 'enabled': False} for name, effect in camera.items()
                if name != 'eye_contact' and effect.get('enabled')]
    if any(effect['effectId'] not in allowed for effect in unwanted):
        raise BroadcastError('An active camera effect cannot be controlled by this gateway')
    if unwanted:
        result = client.call('set_effects', {'effects': unwanted})
        if not result.get('success') or result.get('failed') or result.get('skipped'):
            raise BroadcastError('Could not disable extra camera effects: ' + json.dumps(result))
        state = result['state']; camera = state.get('camera', {})
        changed.append('disabled_extra_camera_effects')
    devices = client.call('list_devices', {'kind': 'camera'})
    if not devices.get('cameras'):
        raise NoCameraDevices('Broadcast reports no camera devices')
    matches = [d for d in devices.get('cameras', []) if d['name'] == 'OBS Virtual Camera']
    if len(matches) != 1:
        raise BroadcastError('Exactly one OBS Virtual Camera input is required')
    device = matches[0]
    desired = {'width': 1280, 'height': 720, 'frameRate': 30}
    same_mode = lambda mode: all(mode.get(k) == v for k, v in desired.items())
    if not any(same_mode(m) for m in device.get('availableResolutions', [])):
        raise BroadcastError('OBS input does not advertise 1280x720 at 30 fps')
    if not device.get('active') or not same_mode(device.get('currentResolution') or {}):
        result = client.call('set_active_device', {'kind': 'camera', 'deviceId': device['id'], **desired})
        if not result.get('success') or result.get('frameRateMismatch'):
            raise BroadcastError('Broadcast did not apply the requested camera mode: ' + json.dumps(result))
        changed.append('selected_obs_720p30')
    if not camera.get('eye_contact', {}).get('enabled'):
        result = client.call('set_effects', {'effects': [{'effectId': 'eye_contact', 'enabled': True}]})
        if not result.get('success') or result.get('failed') or result.get('skipped'):
            raise BroadcastError('Could not enable Eye Contact: ' + json.dumps(result))
        state = result['state']
        changed.append('enabled_eye_contact')
    return {'phase': 'configured', 'camera': device['name'], 'resolution': desired,
            'enabledCameraEffects': [n for n, e in state.get('camera', {}).items() if e.get('enabled')],
            'changed': changed, 'pictureVerified': False}


@contextmanager
def control_lock():
    # Serialize the controller and SSH-triggered commands across processes.
    from settings import data_dir
    with (data_dir() / 'state/broadcast-control.lock').open('a+b') as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BroadcastError('Another Broadcast control operation is running; retry shortly')
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def control(action='status'):
    with control_lock():
        return _control(action)


def _control(action='status'):
    """Called on Windows locally or via SSH. No remote HTTP endpoint is created."""
    client = BroadcastClient()
    try:
        if action == 'status':
            return dict(server=client.info['serverInfo'], **camera_summary(
                client.call('list_devices', {'kind': 'camera'}),
                client.call('get_broadcast_state')))
        if action not in ('prepare', 'restore-live'):
            raise BroadcastError('Unsupported control action')
        return prepare_pipeline(client, restore_live=action == 'restore-live')
    finally:
        client.close()

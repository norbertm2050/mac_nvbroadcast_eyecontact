import copy
import io
import json
import os
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from broadcast_control import BroadcastClient, BroadcastError, prepare_pipeline, control_lock
from picture_health import PictureHealth


class FakeClient:
    def __init__(self):
        self.calls = []
        self.state = {'camera': {'eye_contact': {'enabled': True}, 'background_blur': {'enabled': False}},
                      'microphone': {'studio_voice': {'enabled': True}}}
        self.mode = dict(width=1280, height=720, frameRate=30)
        self.device = dict(id='fresh-id', name='OBS Virtual Camera', active=True,
                           currentResolution=self.mode.copy(), availableResolutions=[self.mode.copy()])
        self.jobs = []
        self.fail = None

    def tools(self):
        return [dict(name=n, inputSchema={'properties': {'effects': {'items': {'properties': {
            'effectId': {'enum': ['eye_contact', 'background_blur']}}}}}})
            for n in ['get_broadcast_state','list_devices','set_effects','set_active_device','get_file_processing_jobs']]

    def call(self, name, arguments=None):
        self.calls.append((name, arguments))
        if name == 'get_broadcast_state': return copy.deepcopy(self.state)
        if name == 'list_devices': return {'cameras': [copy.deepcopy(self.device)]}
        if name == 'get_file_processing_jobs': return {'jobs': self.jobs}
        if name == 'set_effects':
            if arguments.get('action') == 'restore_previous_live':
                self.jobs = []
                return {'event': 'live_effects_restored'}
            if self.fail: return self.fail
            for effect in arguments['effects']:
                self.state['camera'][effect['effectId']]['enabled'] = effect['enabled']
            return {'success': True, 'state': copy.deepcopy(self.state)}
        if name == 'set_active_device':
            return self.fail or {'success': True}
        raise AssertionError(name)


class PipelineTests(unittest.TestCase):
    def test_correct_configuration_does_not_mutate(self):
        client = FakeClient()
        result = prepare_pipeline(client)
        self.assertEqual(result['changed'], [])
        self.assertFalse(result['pictureVerified'])
        self.assertFalse(any(n.startswith('set_') for n, a in client.calls))

    def test_repairs_only_camera_effects(self):
        client = FakeClient()
        client.state['camera']['background_blur']['enabled'] = True
        client.state['camera']['eye_contact']['enabled'] = False
        result = prepare_pipeline(client)
        self.assertEqual(result['enabledCameraEffects'], ['eye_contact'])
        self.assertTrue(client.state['microphone']['studio_voice']['enabled'])

    def test_unsupported_mode_is_not_sent(self):
        client = FakeClient(); client.device['availableResolutions'] = [dict(width=1920,height=1080,frameRate=30)]
        with self.assertRaises(BroadcastError): prepare_pipeline(client)
        self.assertFalse(any(n == 'set_active_device' for n,a in client.calls))

    def test_switch_uses_fresh_id_and_mismatch_is_failure(self):
        client = FakeClient(); client.device['active'] = False
        client.fail = {'success': True, 'frameRateMismatch': True}
        with self.assertRaises(BroadcastError): prepare_pipeline(client)
        self.assertEqual(client.calls[-1][1]['deviceId'], 'fresh-id')

    def test_partial_effect_failure_not_success(self):
        client = FakeClient(); client.state['camera']['eye_contact']['enabled'] = False
        client.fail = {'success': False, 'failed': [{'effectId':'eye_contact','reason':'timeout'}]}
        with self.assertRaises(BroadcastError): prepare_pipeline(client)

    def test_file_processing_is_not_silently_interrupted(self):
        client = FakeClient(); client.jobs = [{'status':'in_progress'}]
        with self.assertRaises(BroadcastError): prepare_pipeline(client)
        self.assertEqual(len(client.calls), 1)


    def test_explicit_restore_can_pause_file_work_before_prepare(self):
        client = FakeClient(); client.jobs = [{'status':'in_progress'}]
        result = prepare_pipeline(client, restore_live=True)
        self.assertEqual(result['changed'], ['live_effects_restored'])
        self.assertEqual(client.calls[0], ('set_effects', {'action':'restore_previous_live'}))


class TransportTests(unittest.TestCase):
    def test_control_lock_serializes_independent_commands(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, EYE_CONTACT_DATA_DIR=folder):
            with control_lock():
                with self.assertRaises(BroadcastError):
                    with control_lock(): pass
            with control_lock(): pass

    def client(self):
        c = BroadcastClient.__new__(BroadcastClient)
        c.port=18100; c.timeout=1; c.session=None; c.version='2024-11-05'; c.sequence=0
        return c

    def test_port_cannot_redirect_to_arbitrary_service(self):
        for value in [80,18110,'18100',True]:
            with self.assertRaises(BroadcastError): BroadcastClient(port=value)

    def test_sse_notification_then_matching_response(self):
        response = Mock(status=200)
        response.getheader.side_effect=lambda name, default=None: 'text/event-stream' if name=='Content-Type' else default
        body=io.BytesIO(b'data: {"method":"notice"}\n\ndata: {"id":1,"result":{"ok":true}}\n\n')
        response.readline.side_effect=body.readline
        with patch('broadcast_control.http.client.HTTPConnection') as connection:
            connection.return_value.getresponse.return_value=response
            self.assertEqual(self.client().request('tools/list'), {'ok': True})
            self.assertEqual(connection.call_args.args[0], '127.0.0.1')

    def test_server_identity_required_before_tool_calls(self):
        with patch.object(BroadcastClient, 'request', return_value={'serverInfo': {'name':'other'}, 'protocolVersion':'2024-11-05'}) as request:
            with self.assertRaises(BroadcastError): BroadcastClient(port=18100)
            request.assert_called_once()

    def test_json_rpc_errors_are_not_success(self):
        response=Mock(status=200)
        response.getheader.side_effect=lambda n, default=None: default
        response.read.return_value=b'{"id":1,"error":{"code":-32602,"message":"bad input"}}'
        with patch('broadcast_control.http.client.HTTPConnection') as connection:
            connection.return_value.getresponse.return_value=response
            with self.assertRaises(BroadcastError): self.client().request('tools/list')


class PictureTests(unittest.TestCase):
    def test_sustained_black_and_recovery(self):
        p=PictureHealth()
        self.assertFalse(p.update(16,0,0))
        self.assertFalse(p.update(16,0,2))
        self.assertTrue(p.update(16,0,3))
        self.assertFalse(p.update(80,20,4))
        self.assertFalse(p.update(16,0,5))

    def test_dark_detailed_picture_is_not_uniform_black(self):
        p=PictureHealth()
        for t in range(10): self.assertFalse(p.update(16,8,t))

import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import network_ready as network


def result(state):
    return subprocess.CompletedProcess([], 0, json.dumps({'BackendState': state}), '')


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.stop = threading.Event()
        self.report = Mock()

    def test_address_classification(self):
        for host in ('pc.example.ts.net.', '100.64.0.1', '100.127.255.254', '[fd7a:115c:a1e0::1]'):
            self.assertTrue(network.uses_tailscale(host), host)
        for host in ('192.168.1.10', '100.128.0.1', 'pc.local', 'ts.net.example.org', '::1'):
            self.assertFalse(network.uses_tailscale(host), host)

    def test_lan_does_not_manage_tailscale(self):
        with patch.object(network, 'find_cli') as find:
            self.assertIsNone(network.ensure_network('192.168.1.10', self.stop, self.report))
            find.assert_not_called()

    def test_stopped_connection_is_restored_and_verified(self):
        with patch.object(network, 'find_cli', return_value='/cli'), patch.object(
            network, 'run_command', side_effect=[result('Stopped'), result(''), result('Running')]
        ) as run:
            self.assertIsNone(network.ensure_network('pc.example.ts.net', self.stop, self.report))
            self.assertEqual(run.call_args_list[1].args[0], ['/cli', 'up'])
            self.assertEqual(run.call_args_list[1].kwargs['timeout'], 15)
            self.report.assert_called_once()

    def test_login_never_initiated_automatically(self):
        with patch.object(network, 'find_cli', return_value='/cli'), patch.object(
            network, 'run_command', return_value=result('NeedsLogin')
        ) as run:
            self.assertIn('登录', network.ensure_network('100.64.0.1', self.stop, self.report))
            self.assertEqual(run.call_count, 1)

    def test_missing_cli_and_timeout_are_actionable(self):
        with patch.object(network, 'find_cli', return_value=None):
            self.assertIn('安装', network.ensure_network('100.64.0.1', self.stop, self.report))
        with patch.object(network, 'find_cli', return_value='/cli'), patch.object(
            network, 'run_command', side_effect=subprocess.TimeoutExpired('private command', 8)
        ):
            message = network.ensure_network('100.64.0.1', self.stop, self.report)
            self.assertIn('超时', message)
            self.assertNotIn('private', message)

    def test_stop_prevents_connecting(self):
        self.stop.set()
        with patch.object(network, 'find_cli') as find:
            network.ensure_network('100.64.0.1', self.stop, self.report)
            find.assert_not_called()

    def test_healthy_video_skips_commands_and_clears_message(self):
        def report(message):
            self.assertIsNone(message)
            self.stop.set()
        with patch.object(network, 'ensure_network') as ensure:
            network.watch_network('100.64.0.1', self.stop, lambda: True, report)
            ensure.assert_not_called()


if __name__ == '__main__':
    unittest.main()

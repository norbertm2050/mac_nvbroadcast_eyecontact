import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import av
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from resilient_decode import decode_resilient


def packet(key=True, size=100):
    return SimpleNamespace(is_keyframe=key, size=size)


class RecoveryTests(unittest.TestCase):
    def run_decoder(self, packets, factory, **kw):
        container = SimpleNamespace(demux=lambda stream: iter(packets))
        return list(decode_resilient(container, object(), factory=factory, **kw))

    def test_transient_error_waits_for_keyframe_without_reopening_network(self):
        bad = Mock(is_hwaccel=True)
        bad.decode.side_effect = av.error.InvalidDataError(1094995529, 'bad frame')
        good = Mock(is_hwaccel=True)
        good.decode.return_value = ['recovered']
        factory = Mock(side_effect=[bad, good])
        result = self.run_decoder([packet(False), packet(), packet(False), packet(), packet(size=0)], factory)
        self.assertEqual(result, [('recovered', 'videotoolbox')])
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(good.decode.call_count, 1)

    def test_three_errors_fall_back_and_later_restore_hardware(self):
        bad = Mock(is_hwaccel=True)
        bad.decode.side_effect = av.error.InvalidDataError(1, 'bad frame')
        software = Mock(is_hwaccel=False)
        software.decode.return_value = ['software frame']
        hardware = Mock(is_hwaccel=True)
        hardware.decode.return_value = ['hardware frame']
        factory = Mock(side_effect=[bad, bad, bad, software, hardware])
        now = [0]
        def packets():
            for _ in range(4):
                yield packet()
            now[0] = 61
            yield packet()
        result = self.run_decoder(packets(), factory, clock=lambda: now[0])
        self.assertEqual(result, [('software frame', 'software'), ('hardware frame', 'videotoolbox')])
        self.assertEqual([c.args[1] for c in factory.call_args_list], ['videotoolbox']*3+['software','videotoolbox'])

    def test_failed_hardware_probe_keeps_software_keyframe(self):
        bad = Mock(is_hwaccel=True)
        bad.decode.side_effect = av.error.InvalidDataError(1, 'bad frame')
        software = Mock(is_hwaccel=False)
        software.decode.return_value = ['ok']
        factory = Mock(side_effect=[bad, bad, bad, software, bad])
        now = [0]
        def packets():
            for _ in range(4):
                yield packet()
            now[0] = 61
            yield packet()
            yield packet(False)
        result = self.run_decoder(packets(), factory, clock=lambda: now[0])
        self.assertEqual(result, [('ok', 'software')]*3)
        self.assertEqual(factory.call_count, 5)

    def test_network_error_propagates(self):
        def demux(stream):
            raise TimeoutError('network timeout')
        with self.assertRaises(TimeoutError):
            list(decode_resilient(SimpleNamespace(demux=demux), object()))

    def test_software_configuration_never_probes_hardware(self):
        decoder = Mock(is_hwaccel=False)
        decoder.decode.return_value = ['ok']
        factory = Mock(return_value=decoder)
        self.assertEqual(self.run_decoder([packet(),packet()],factory,acceleration='software'), [('ok','software')]*2)
        factory.assert_called_once()

    def test_repeated_software_failure_requests_connection_refresh(self):
        decoder = Mock(is_hwaccel=False)
        decoder.decode.side_effect = av.error.InvalidDataError(1, 'bad stream parameters')
        factory = Mock(return_value=decoder)
        with self.assertRaises(av.error.InvalidDataError):
            self.run_decoder([packet()]*4, factory, acceleration='software')
        self.assertEqual(factory.call_count, 3)

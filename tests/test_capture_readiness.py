import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from capture_readiness import CaptureReadiness, receiver_is_live

class ReadinessTests(unittest.TestCase):
    def test_requires_continuous_warmup_and_rewarms_after_loss(self):
        gate = CaptureReadiness(3)
        self.assertFalse(gate.update(True, 10))
        self.assertFalse(gate.update(True, 12))
        self.assertTrue(gate.update(True, 13))
        self.assertTrue(gate.update(False, 14))
        self.assertFalse(gate.update(False, 15))
        self.assertFalse(gate.update(True, 20))
        self.assertTrue(gate.update(True, 23))

    def test_missing_malformed_and_stale_samples_are_not_live(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'receiver.json'
            self.assertFalse(receiver_is_live(p, 10))
            p.write_text('{')
            self.assertFalse(receiver_is_live(p, 10))
            for sample in [{}, {'updated':7,'fresh':True,'fps':30},
                           {'updated':11,'fresh':True,'fps':30},
                           {'updated':10,'fresh':False,'fps':30},
                           {'updated':10,'fresh':True,'fps':0}]:
                p.write_text(json.dumps(sample))
                self.assertFalse(receiver_is_live(p, 10), sample)
            p.write_text(json.dumps({'updated':9,'fresh':True,'fps':29.8}))
            self.assertTrue(receiver_is_live(p, 10))

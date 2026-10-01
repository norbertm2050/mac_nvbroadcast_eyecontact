import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from video_readiness import VideoReadiness

class VideoReadinessTests(unittest.TestCase):
    def test_initial_warmup_requires_continuous_flow(self):
        r=VideoReadiness()
        self.assertFalse(r.update(True,True,0))
        self.assertFalse(r.update(True,False,2))
        self.assertFalse(r.update(True,True,3))
        self.assertFalse(r.update(True,True,5))
        self.assertTrue(r.update(True,True,6))

    def test_live_throughput_dip_does_not_blank_output(self):
        r=VideoReadiness()
        r.update(True,True,0)
        self.assertTrue(r.update(True,True,3))
        self.assertTrue(r.update(True,False,4))
        self.assertTrue(r.update(True,False,10))

    def test_stale_output_is_blanked_and_recovers_quickly(self):
        r=VideoReadiness()
        r.update(True,True,0);r.update(True,True,3)
        self.assertFalse(r.update(False,True,4))
        self.assertFalse(r.update(True,False,5))
        self.assertFalse(r.update(True,True,6))
        self.assertFalse(r.update(True,True,6.4))
        self.assertTrue(r.update(True,True,6.5))

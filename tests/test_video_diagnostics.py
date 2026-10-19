import json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from video_diagnostics import VideoDiagnostics

class DiagnosticsTests(unittest.TestCase):
    def test_elapsed_active_and_completed_stats(self):
        now=[1.];d=VideoDiagnostics(clock=lambda:now[0])
        with d.span('encode'):
            now[0]=1.25
            self.assertEqual(d.snapshot()['activeMs']['encode'],250)
        result=d.snapshot()
        self.assertEqual(result['stages']['encode']['maxMs'],250)
        self.assertEqual(result['activeMs'],{})
        self.assertEqual(d.snapshot()['stages'],{})

    def test_exception_does_not_leave_active_stage(self):
        d=VideoDiagnostics()
        with self.assertRaises(ValueError):
            with d.span('read'):raise ValueError('expected')
        self.assertEqual(d.snapshot()['activeMs'],{})

    def test_event_queue_is_bounded(self):
        d=VideoDiagnostics()
        for i in range(200):d.event('transition',number=i)
        snapshot=d.snapshot()
        self.assertEqual(len(snapshot['events']),128)
        self.assertEqual(snapshot['droppedEvents'],72)

    def test_private_config_excluded_and_errors_scrubbed_and_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=VideoDiagnostics();d.start(Path(tmp),{'host':'private.example','token':'secret-token','camera':'private-camera','width':1280})
            d.write({'error':'failed rtsp://eye:secret-token@private.example:8554/raw'})
            path=Path(tmp)/'video-diagnostics.jsonl';content=path.read_text()
            self.assertNotIn('secret-token',content)
            self.assertNotIn('private-camera',content)
            self.assertNotIn('private.example',content.splitlines()[0])
            self.assertEqual(json.loads(content.splitlines()[0])['config']['width'],1280)
            handler=d.logger.handlers[0];handler.maxBytes=200;handler.backupCount=2
            for _ in range(10):d.write({'kind':'health','data':'x'*100})
            d.close()
            self.assertLessEqual(len(list(Path(tmp).iterdir())),3)

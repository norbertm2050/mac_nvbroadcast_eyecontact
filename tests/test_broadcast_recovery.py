import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from broadcast_recovery import BroadcastRecovery
from broadcast_control import NoCameraDevices, prepare_pipeline, BroadcastError
from test_broadcast_control import FakeClient

class RecoveryTests(unittest.TestCase):
    def test_confirmations_cooldown_and_limit(self):
        r=BroadcastRecovery()
        self.assertFalse(r.observe(True,True,0))
        self.assertFalse(r.observe(True,True,15))
        self.assertTrue(r.observe(True,True,30))
        for t in [45,60,75,300]: self.assertFalse(r.observe(True,True,t))
        self.assertTrue(r.observe(True,True,330))
        for t in [345,660,10000]:self.assertFalse(r.observe(True,True,t))
        self.assertEqual(r.attempts,2)
    def test_healthy_or_disconnected_input_breaks_streak(self):
        for missing,live in [(False,True),(True,False)]:
            r=BroadcastRecovery();r.observe(True,True,0);r.observe(True,True,15)
            self.assertFalse(r.observe(missing,live,30))
            self.assertFalse(r.observe(True,True,45))
            self.assertFalse(r.observe(True,True,60))
            self.assertTrue(r.observe(True,True,75))
    def test_empty_devices_distinct_from_wrong_device(self):
        c=FakeClient();original=c.call
        c.call=lambda n,a=None: {'cameras':[]} if n=='list_devices' else original(n,a)
        with self.assertRaises(NoCameraDevices):prepare_pipeline(c)
        c=FakeClient();c.device['name']='Physical camera'
        with self.assertRaises(BroadcastError) as e:prepare_pipeline(c)
        self.assertNotIsInstance(e.exception,NoCameraDevices)
    def test_file_job_prevents_recovery_signal(self):
        c=FakeClient();c.jobs=[{'id':'busy'}];original=c.call
        c.call=lambda n,a=None: {'cameras':[]} if n=='list_devices' else original(n,a)
        with self.assertRaises(BroadcastError) as e:prepare_pipeline(c)
        self.assertNotIsInstance(e.exception,NoCameraDevices)

    def test_controller_recovery_reopens_sender_and_logs(self):
        import ast, threading, json, tempfile
        from unittest.mock import Mock
        from types import SimpleNamespace
        source=(Path(__file__).resolve().parents[1]/'src/windows_app.py').read_text()
        tree=ast.parse(source)
        window=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        method=next(n for n in window.body if isinstance(n,ast.FunctionDef) and n.name=='check_broadcast')
        clock=Mock();clock.monotonic.side_effect=lambda: now[0]
        clock.time.return_value=100
        control=Mock(side_effect=NoCameraDevices('empty'))
        restart=Mock()
        class Immediate:
            def __init__(self,target,**kwargs):self.target=target
            def start(self):self.target()
        from settings import atomic_json
        namespace=dict(time=clock,threading=SimpleNamespace(Thread=Immediate),
                       receiver_is_live=lambda p:True,ensure_broadcast=lambda:None,
                       control=control,NoCameraDevices=NoCameraDevices,
                       restart_broadcast=restart,atomic_json=atomic_json)
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<controller test>','exec'),namespace)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'state').mkdir()
            w=SimpleNamespace(home=root,broadcast_pending=False,last_broadcast_check=0,
                              want_running=True,broadcast_recovery=BroadcastRecovery(),
                              reopen_sender=threading.Event())
            now=[15]
            for now[0] in [15,30,45]:namespace['check_broadcast'](w)
            restart.assert_called_once()
            self.assertTrue(w.reopen_sender.is_set())
            result=json.loads((root/'state/broadcast-control.json').read_text())
            self.assertEqual(result['phase'],'recovering')
            self.assertEqual(result['recoveryAttempts'],1)
            control.side_effect=BroadcastError('network timeout')
            for now[0] in [400,415,430]:namespace['check_broadcast'](w)
            restart.assert_called_once()

    def test_resume_hint_invalidates_only_video_handles(self):
        import ast
        from unittest.mock import Mock
        from types import SimpleNamespace
        source=(Path(__file__).resolve().parents[1]/'src/windows_app.py').read_text()
        window=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Window')
        method=next(n for n in window.body if isinstance(n,ast.FunctionDef) and n.name=='poll')
        method.body=method.body[:4]  # Complete resume detection branch; omit normal UI polling.
        clock=Mock();clock.monotonic.return_value=100;clock.time.return_value=100
        write=Mock();namespace=dict(time=clock,atomic_json=write)
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<resume test>','exec'),namespace)
        children={role:Mock() for role in ['receiver','sender','mediamtx']}
        for child in children.values():child.poll.return_value=None
        w=SimpleNamespace(last_poll_time=1,want_running=True,running=True,resume_events=0,
                          last_broadcast_check=90,broadcast_recovery=BroadcastRecovery(),
                          home=Path('/unused'),children=children)
        namespace['poll'](w)
        self.assertEqual(w.resume_events,1)
        for role in ['receiver','sender']:children[role].kill.assert_called_once()
        children['mediamtx'].kill.assert_not_called()
        self.assertEqual(write.call_args.args[1]['pauseSeconds'],99)
        namespace['poll'](w)
        self.assertEqual(w.resume_events,1)
        w.want_running=False;w.last_poll_time=0;namespace['poll'](w)
        self.assertEqual(w.resume_events,1)

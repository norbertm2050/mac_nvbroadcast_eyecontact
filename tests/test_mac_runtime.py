import sys
from pathlib import Path
from unittest.mock import Mock,patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mac_runtime import VideoActivity

class ActivityTests(unittest.TestCase):
 def test_release_is_idempotent(self):
  lib=Mock();lib.eye_activity_begin.return_value=123;lib.eye_video_thread.return_value=0
  with patch('mac_runtime.ctypes.CDLL',return_value=lib):
   activity=VideoActivity();activity.video_thread();activity.close();activity.close()
  lib.eye_activity_end.assert_called_once_with(123)
 def test_missing_token_is_reported(self):
  lib=Mock();lib.eye_activity_begin.return_value=None
  with patch('mac_runtime.ctypes.CDLL',return_value=lib),self.assertRaises(RuntimeError):VideoActivity()

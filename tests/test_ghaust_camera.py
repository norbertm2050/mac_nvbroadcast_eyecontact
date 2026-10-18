import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ghaust_camera import Camera
from settings import load_config

class GhaustTests(unittest.TestCase):
    def test_transport_remains_720p_while_output_is_1080(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, EYE_CONTACT_DATA_DIR=folder), patch('settings.sys.platform','darwin'):
            Path(folder,'config.json').write_text(json.dumps({'virtual_backend':'ghaust'}))
            c=load_config()
            self.assertEqual((c['width'],c['height'],c['fps']),(1280,720,30))
            self.assertEqual((c['output_width'],c['output_height'],c['virtual_pixel_format']),(1920,1080,'bgra'))

    def test_reject_wrong_frame_and_close_handle(self):
        lib=Mock();lib.eye_sink_open.return_value=123;lib.eye_sink_send.return_value=0
        with patch('ghaust_camera.ctypes.CDLL',return_value=lib):
            with Camera() as cam:
                with self.assertRaises(ValueError):cam.send(np.zeros((720,1280,4),np.uint8))
                lib.eye_sink_send.assert_not_called()
                cam.send(np.zeros((1080,1920,4),np.uint8))
                self.assertEqual(lib.eye_sink_send.call_count,1)
            lib.eye_sink_close.assert_called_once_with(123)

    def test_missing_extension_is_an_error_not_silent_obs_fallback(self):
        lib=Mock();lib.eye_sink_open.return_value=None
        with patch('ghaust_camera.ctypes.CDLL',return_value=lib), self.assertRaises(RuntimeError):Camera()

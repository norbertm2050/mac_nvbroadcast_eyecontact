"""Direct CMIO sink adapter for separately installed GhaustCam 1.0.

Its advertised sink accepts 1920x1080 BGRA. No OBS device is opened.
"""
import ctypes
from pathlib import Path
import sys
import numpy as np


class Camera:
    def __init__(self):
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'build'))
        self.lib = ctypes.CDLL(str(root / 'libeye_cmio.dylib'))
        self.lib.eye_sink_open.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.lib.eye_sink_open.restype = ctypes.c_void_p
        self.lib.eye_sink_send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        self.lib.eye_sink_close.argtypes = [ctypes.c_void_p]
        error = ctypes.c_int()
        self.handle = self.lib.eye_sink_open(1920, 1080, ctypes.byref(error))
        if not self.handle:
            raise RuntimeError(f'GhaustCam output unavailable ({error.value}); activate its camera extension first')
        self.device = 'GhaustCam (direct CMIO sink)'

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.lib.eye_sink_close(self.handle)
        self.handle = None

    def send(self, frame):
        if frame.shape != (1080, 1920, 4) or frame.dtype != np.uint8:
            raise ValueError('GhaustCam requires 1920x1080 BGRA uint8')
        frame = np.ascontiguousarray(frame)
        result = self.lib.eye_sink_send(self.handle, frame.ctypes.data, frame.strides[0])
        # A full bounded queue / pool drops this frame rather than building latency.
        if result not in (0, 1, -6689):
            raise RuntimeError(f'GhaustCam frame submission failed ({result})')

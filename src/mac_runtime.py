"""Keep active video work out of App Nap; release the assertion on shutdown."""
import ctypes
from pathlib import Path
import sys


class VideoActivity:
    def __init__(self):
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'build'))
        self.lib = ctypes.CDLL(str(root / 'libeye_cmio.dylib'))
        self.lib.eye_activity_begin.restype = ctypes.c_void_p
        self.lib.eye_activity_end.argtypes = [ctypes.c_void_p]
        self.lib.eye_activity_end.restype = None
        self.lib.eye_video_thread.restype = ctypes.c_int
        self.handle = self.lib.eye_activity_begin()
        if not self.handle:
            raise RuntimeError('Cannot start live video activity')

    def video_thread(self):
        result = self.lib.eye_video_thread()
        if result:
            raise RuntimeError(f'Cannot set video thread scheduling ({result})')

    def close(self):
        if self.handle:
            self.lib.eye_activity_end(self.handle)
            self.handle = None

"""Bounded stage statistics; only the monitor thread writes rotating JSON logs."""
import collections
from contextlib import contextmanager
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
import uuid
from settings import safe_error


class VideoDiagnostics:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.stages = {}
        self.active = {}
        self.last = {}
        self.events = collections.deque(maxlen=128)
        self.dropped_events = 0
        self.logger = None
        self.session = uuid.uuid4().hex

    @contextmanager
    def span(self, stage):
        started = self.clock()
        with self.lock:
            self.active[stage] = started
        try:
            yield
        finally:
            now = self.clock()
            with self.lock:
                self.active.pop(stage, None)
                s = self.stages.setdefault(stage, {'count': 0, 'totalMs': 0., 'maxMs': 0., 'gapMaxMs': 0.})
                elapsed = (now - started) * 1000
                s['count'] += 1
                s['totalMs'] += elapsed
                s['maxMs'] = max(s['maxMs'], elapsed)
                if stage in self.last:
                    s['gapMaxMs'] = max(s['gapMaxMs'], (now - self.last[stage]) * 1000)
                self.last[stage] = now

    def event(self, kind, **fields):
        with self.lock:
            if len(self.events) == self.events.maxlen:
                self.dropped_events += 1
            self.events.append(dict(kind=kind, monotonic=self.clock(), **fields))

    def snapshot(self):
        now = self.clock()
        with self.lock:
            stages = self.stages
            self.stages = {}
            result = {
                'stages': {k: dict(count=v['count'], meanMs=round(v['totalMs']/v['count'], 3),
                                   maxMs=round(v['maxMs'], 3), gapMaxMs=round(v['gapMaxMs'], 3))
                           for k, v in stages.items()},
                'activeMs': {k: round((now-v)*1000, 3) for k, v in self.active.items()},
                'lastCompletionAgeMs': {k: round((now-v)*1000, 3) for k, v in self.last.items()},
                'events': list(self.events), 'droppedEvents': self.dropped_events,
            }
            self.events.clear()
            self.dropped_events = 0
            return result

    def start(self, directory, config):
        path = directory / 'video-diagnostics.jsonl'
        self.logger = logging.Logger('video-diagnostics-' + self.session)
        handler = RotatingFileHandler(path, maxBytes=16*1024*1024, backupCount=5, encoding='utf-8')
        os.chmod(path, 0o600)
        self.logger.addHandler(handler)
        # Deliberate allowlist: no address, connection code, camera name or image data.
        keys = ['width', 'height', 'fps', 'bitrate', 'virtual_backend', 'virtual_pixel_format',
                'output_width', 'output_height', 'decode_acceleration', 'warmup_seconds']
        self.write({'kind': 'startup', 'config': {k: config.get(k) for k in keys},
                    'networkKind': 'tailscale' if '.ts.net' in config.get('host', '') else 'other',
                    'freshnessLimitMs': 750})

    def write(self, record):
        if self.logger:
            record = dict(record, time=time.time(), pid=os.getpid(), session=self.session)
            # Also scrub credentials in nested error strings from FFmpeg.
            self.logger.info(safe_error(json.dumps(record, ensure_ascii=False)))

    def close(self):
        if self.logger:
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)

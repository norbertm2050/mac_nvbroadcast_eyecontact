"""Require live receiver frames before opening Broadcast's output device."""

import json
import time


def receiver_is_live(path, now=None):
    try:
        sample = json.loads(path.read_text())
        age = (time.time() if now is None else now) - sample["updated"]
        return 0 <= age < 3 and sample.get("fresh") is True and sample.get("fps", 0) > 0
    except (OSError, ValueError, KeyError, TypeError):
        return False


class CaptureReadiness:
    def __init__(self, warmup=3, disconnect_grace=2):
        self.warmup = warmup
        self.disconnect_grace = disconnect_grace
        self.since = None
        self.last_live = None
        self.ready = False

    def update(self, live, now):
        if not live:
            if self.ready and self.last_live is not None and now - self.last_live < self.disconnect_grace:
                return True
            self.since = None
            self.ready = False
            return False
        self.last_live = now
        if self.since is None:
            self.since = now
        self.ready = now - self.since >= self.warmup
        return self.ready

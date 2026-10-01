"""Warm up once; throughput fluctuations must not blank a live video stream."""


class VideoReadiness:
    def __init__(self, warmup=3, recovery=0.5):
        self.warmup = warmup
        self.recovery = recovery
        self.since = None
        self.ready = False
        self.previously_ready = False

    def update(self, fresh, flowing, now):
        if not fresh:
            self.ready = False
            self.since = None
            return False
        if self.ready:
            return True
        if not flowing:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        delay = self.recovery if self.previously_ready else self.warmup
        self.ready = now - self.since >= delay
        self.previously_ready |= self.ready
        return self.ready

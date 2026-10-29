"""Bound recovery of a confirmed empty Broadcast device enumeration."""


class BroadcastRecovery:
    def __init__(self, confirmations=3, cooldown=300, limit=2):
        self.confirmations = confirmations
        self.cooldown = cooldown
        self.limit = limit
        self.failures = 0
        self.attempts = 0
        self.last_attempt = None

    def observe(self, missing_cameras, live_input, now):
        if not missing_cameras or not live_input:
            self.failures = 0
            return False
        self.failures += 1
        if self.failures < self.confirmations or self.attempts >= self.limit:
            return False
        if self.last_attempt is not None and now - self.last_attempt < self.cooldown:
            return False
        self.attempts += 1
        self.last_attempt = now
        self.failures = 0
        return True

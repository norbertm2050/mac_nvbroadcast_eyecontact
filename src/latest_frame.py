"""A single replaceable frame slot; producers never wait for slow consumers."""

import threading
import time


class LatestFrame:
    def __init__(self):
        self._condition = threading.Condition()
        self._item = None
        self._closed = False

    def put(self, frame):
        with self._condition:
            if self._closed:
                return
            self._item = (time.monotonic(), frame)
            self._condition.notify_all()

    def peek(self):
        with self._condition:
            return self._item

    def wait(self, after=0, timeout=1):
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    self._closed or (self._item is not None and self._item[0] != after)
                ),
                timeout,
            )
            if self._closed or self._item is None or self._item[0] == after:
                return None
            return self._item

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()

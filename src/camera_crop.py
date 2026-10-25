"""Centered area crop in packed YUV, before the existing encode conversion."""
import math
import json
import time

import av
from video_pixels import uyvy_view


def crop_denominator(value):
    return value if type(value) is int and 1 <= value <= 5 else 1


def area_percent(config):
    value = config.get("crop_area_percent", 100 / crop_denominator(config.get("crop_area_denominator")))
    if type(value) not in (int, float) or not math.isfinite(value):
        return 100.0
    return max(20.0, min(100.0, float(value)))


class LiveCropSelection:
    """Rate-limit config reads without slowing down frames or opening a new queue."""
    def __init__(self, path, config):
        self.path, self.value, self.next_read = path, area_percent(config), 0.0

    def read(self):
        now = time.monotonic()
        if now >= self.next_read:
            self.next_read = now + .1
            try:
                self.value = area_percent(json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        return self.value


def crop_rect(width, height, percent):
    percent = area_percent({"crop_area_percent": percent})
    if percent == 100:
        return 0, 0, width, height
    # Retain the exact aspect ratio, even dimensions and chroma-aligned center.
    divisor = math.gcd(width, height)
    unit_w, unit_h = width // divisor, height // divisor
    candidates = [k for k in range(1, divisor + 1)
                  if unit_w*k % 2 == 0 and unit_h*k % 2 == 0
                  and (width-unit_w*k) % 4 == 0
                  and (height-unit_h*k) % 2 == 0]
    k = min(candidates, key=lambda k: abs(k-divisor*math.sqrt(percent/100))) if candidates else divisor
    w, h = unit_w*k, unit_h*k
    return (width-w)//2, (height-h)//2, w, h


def crop_frame(frame, percent):
    rect = crop_rect(frame.width, frame.height, percent)
    x, y, w, h = rect
    if w == frame.width and h == frame.height:
        return frame, rect
    result = av.VideoFrame(w, h, "uyvy422")
    uyvy_view(result)[:] = uyvy_view(frame)[y:y+h, x:x+w]
    result.color_range = frame.color_range
    result.colorspace = frame.colorspace
    return result, rect

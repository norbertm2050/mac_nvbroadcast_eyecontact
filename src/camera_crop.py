"""Centered area crop in packed YUV, before the existing encode conversion."""
import math

import av
from video_pixels import uyvy_view


def crop_denominator(value):
    return value if type(value) is int and 1 <= value <= 5 else 1


def crop_rect(width, height, denominator):
    denominator = crop_denominator(denominator)
    if denominator == 1:
        return 0, 0, width, height
    # Retain the exact aspect ratio, even dimensions and chroma-aligned center.
    divisor = math.gcd(width, height)
    unit_w, unit_h = width // divisor, height // divisor
    candidates = [k for k in range(1, divisor + 1)
                  if unit_w*k % 2 == 0 and unit_h*k % 2 == 0
                  and (width-unit_w*k) % 4 == 0
                  and (height-unit_h*k) % 2 == 0]
    k = min(candidates, key=lambda k: abs(k-divisor/math.sqrt(denominator))) if candidates else divisor
    w, h = unit_w*k, unit_h*k
    return (width-w)//2, (height-h)//2, w, h


def crop_frame(frame, denominator):
    rect = crop_rect(frame.width, frame.height, denominator)
    x, y, w, h = rect
    if w == frame.width and h == frame.height:
        return frame, rect
    result = av.VideoFrame(w, h, "uyvy422")
    uyvy_view(result)[:] = uyvy_view(frame)[y:y+h, x:x+w]
    result.color_range = frame.color_range
    result.colorspace = frame.colorspace
    return result, rect

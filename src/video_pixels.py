"""Expose packed UYVY planes without an RGB round trip or a numpy copy."""

import numpy as np


def uyvy_view(frame):
    if frame.format.name != "uyvy422":
        frame = frame.reformat(format="uyvy422")
    plane = frame.planes[0]
    # ndarray keeps the plane (and hence AVFrame storage) alive after this call.
    return np.ndarray(
        (frame.height, frame.width, 2),
        dtype=np.uint8,
        buffer=plane,
        strides=(plane.line_size, 2, 1),
    )

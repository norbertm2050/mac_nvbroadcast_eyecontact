"""Encoder configuration validated on this Mac's VideoToolbox implementation."""


def mac_encoder_options():
    # Do not force max_ref_frames=1 with low_delay: on this M5/FFmpeg build
    # 60 submitted frames produced only 30 all-I packets. Automatic references
    # preserve the one-frame-in/one-packet-out low-latency path (I/P, no B frames).
    return {
        "flags": "low_delay",
        "realtime": "1",
        "prio_speed": "1",
        "profile": "high",
        "allow_sw": "0",
        "max_ref_frames": "0",
    }

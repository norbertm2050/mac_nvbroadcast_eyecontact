"""Recover a decoder at keyframes without tearing down a healthy RTSP session."""
import time
import av
from av.codec.hwaccel import HWAccel


def make_decoder(stream, acceleration):
    hw = HWAccel(acceleration, allow_software_fallback=False) if acceleration != 'software' else None
    decoder = av.CodecContext.create(stream.codec_context.name, 'r', hwaccel=hw)
    decoder.extradata = stream.codec_context.extradata
    decoder.thread_count = 1
    decoder.open()
    return decoder


def decode_resilient(container, stream, acceleration='videotoolbox', report=None,
                     factory=make_decoder, clock=time.monotonic, retry_seconds=60):
    """Yield (frame, actual_acceleration); probe hardware without dropping good software output.

    Three failures without 150 successful frames trigger a software cooldown.
    Network/demux errors still propagate to the connection owner.
    """
    report = report or (lambda **event: None)
    decoder = None
    mode = acceleration
    failures = 0
    software_failures = 0
    good_frames = 0
    retry_at = 0
    for packet in container.demux(stream):
        # demux emits an empty drain packet at EOF; it is not a live video frame.
        if not packet.size:
            continue
        probing = (mode == 'software' and acceleration != 'software'
                   and clock() >= retry_at and packet.is_keyframe and decoder is not None)
        if decoder is None and not packet.is_keyframe:
            continue
        if probing:
            try:
                candidate = factory(stream, acceleration)
                frames = list(candidate.decode(packet))
                if frames:
                    decoder = candidate
                    mode = acceleration
                    good_frames = 0
                    failures = 0
                    report(event='hardware_restored', acceleration=mode)
                    for frame in frames:
                        yield frame, mode
                    continue
            except av.error.FFmpegError as error:
                report(event='hardware_probe_failed', error=str(error))
            retry_at = clock() + retry_seconds
            # The old software decoder has not consumed this keyframe yet.
        try:
            if decoder is None:
                decoder = factory(stream, mode)
            frames = list(decoder.decode(packet))
        except av.error.FFmpegError as error:
            decoder = None
            good_frames = 0
            if mode != 'software':
                failures += 1
                if failures >= 3:
                    mode = 'software'
                    retry_at = clock() + retry_seconds
            else:
                software_failures += 1
                if software_failures >= 3:
                    # Refresh RTSP stream parameters instead of silently looping
                    # forever if neither decoder can consume the stream.
                    raise
            report(event='decoder_reset', error=str(error), acceleration=mode,
                   failures=failures)
            continue
        good_frames += len(frames)
        if frames:
            software_failures = 0
        if good_frames >= 150:
            failures = 0
        actual = mode if decoder.is_hwaccel else 'software'
        for frame in frames:
            yield frame, actual

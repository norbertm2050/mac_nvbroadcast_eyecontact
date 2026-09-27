"""Start each decoder connection at an independently decodable keyframe."""


def decode_from_keyframe(container, stream):
    # RTSP probing may already have submitted a partial GOP to the decoder.
    # A keyframe gate alone does not clear that state (VideoToolbox -12909).
    stream.codec_context.flush_buffers()
    started = False
    for packet in container.demux(stream):
        if not started:
            if not packet.is_keyframe:
                continue
            started = True
        yield from packet.decode()

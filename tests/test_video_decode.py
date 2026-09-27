import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from video_decode import decode_from_keyframe


class DecoderTests(unittest.TestCase):
    def test_flush_probe_state_then_wait_for_keyframe(self):
        events = []

        class Context:
            def flush_buffers(self):
                events.append("flush")

        class Stream:
            codec_context = Context()

        class Packet:
            def __init__(self, name, key):
                self.name = name
                self.is_keyframe = key

            def decode(self):
                events.append(self.name)
                return [self.name]

        class Container:
            def demux(self, stream):
                return iter(
                    [
                        Packet("partial P", False),
                        Packet("IDR", True),
                        Packet("P", False),
                    ]
                )

        frames = list(decode_from_keyframe(Container(), Stream()))
        self.assertEqual(frames, ["IDR", "P"])
        self.assertEqual(events, ["flush", "IDR", "P"])


if __name__ == "__main__":
    unittest.main()

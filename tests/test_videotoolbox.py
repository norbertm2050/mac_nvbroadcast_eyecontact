"""Optional hardware regression: RUN_VIDEO_HARDWARE_TESTS=1 python -m unittest ..."""

import os, sys, tempfile, unittest, fractions
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import av, numpy as np
from video_codec import mac_encoder_options


@unittest.skipUnless(
    sys.platform == "darwin" and os.getenv("RUN_VIDEO_HARDWARE_TESTS") == "1",
    "requires Mac VideoToolbox hardware",
)
class VideoToolboxTests(unittest.TestCase):
    def test_thirty_fps_input_does_not_silently_become_fifteen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "sample.h264")
            pts = []
            with av.open(path, "w", format="h264") as output:
                stream = output.add_stream("h264_videotoolbox", rate=30)
                stream.width = 1280
                stream.height = 720
                stream.pix_fmt = "nv12"
                stream.bit_rate = 6000000
                stream.codec_context.max_b_frames = 0
                stream.codec_context.gop_size = 30
                stream.codec_context.time_base = fractions.Fraction(1, 30)
                stream.options = mac_encoder_options()
                for i in range(60):
                    f = av.VideoFrame.from_ndarray(
                        np.full((720, 1280, 3), i * 3, np.uint8), format="rgb24"
                    ).reformat(format="nv12")
                    f.pts = i
                    f.time_base = fractions.Fraction(1, 30)
                    for p in stream.encode(f):
                        pts.append(p.pts)
                        output.mux(p)
                for p in stream.encode(None):
                    pts.append(p.pts)
                    output.mux(p)
            self.assertEqual(pts, list(range(60)))
            with av.open(path) as video:
                types = [f.pict_type for f in video.decode(video=0)]
            self.assertEqual(len(types), 60)
            self.assertGreater(types.count(av.video.frame.PictureType.P), 50)
            self.assertNotIn(av.video.frame.PictureType.B, types)


if __name__ == "__main__":
    unittest.main()

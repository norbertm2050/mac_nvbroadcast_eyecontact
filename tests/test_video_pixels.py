import gc, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import av, numpy as np
from video_pixels import uyvy_view


class PixelsTests(unittest.TestCase):
    def test_padding_and_lifetime(self):
        frame = av.VideoFrame(18, 4, "uyvy422")
        plane = frame.planes[0]
        raw = np.full((4, plane.line_size), 255, np.uint8)
        for row in range(4):
            raw[row, :36] = row + 20
        plane.update(raw.tobytes())
        view = uyvy_view(frame)
        del plane, frame
        gc.collect()
        self.assertEqual(view.shape, (4, 18, 2))
        for row in range(4):
            self.assertTrue(np.all(view[row] == row + 20))
        self.assertEqual(np.ascontiguousarray(view).nbytes, 4 * 18 * 2)

    def test_yuv_black_remains_black(self):
        f = av.VideoFrame.from_ndarray(np.zeros((4, 32, 3), np.uint8), format="rgb24")
        data = uyvy_view(f)
        self.assertTrue(np.all(np.abs(data[:, :, 0].astype(int) - 128) <= 1))
        self.assertTrue(np.all(data[:, :, 1] <= 17))


if __name__ == "__main__":
    unittest.main()

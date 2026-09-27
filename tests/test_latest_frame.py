import sys, threading, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from latest_frame import LatestFrame


class LatestFrameTests(unittest.TestCase):
    def test_slow_consumer_gets_only_newest(self):
        slot = LatestFrame()
        for i in range(100):
            slot.put(i)
        item = slot.wait()
        self.assertEqual(item[1], 99)
        self.assertIsNone(slot.wait(item[0], timeout=0))
        slot.put(100)
        self.assertEqual(slot.wait(item[0], timeout=0)[1], 100)

    def test_producer_wakes_waiting_consumer(self):
        slot = LatestFrame()
        result = []
        started = threading.Event()

        def consume():
            started.set()
            result.append(slot.wait(timeout=2))

        t = threading.Thread(target=consume)
        t.start()
        started.wait(1)
        slot.put("frame")
        t.join(1)
        self.assertFalse(t.is_alive())
        self.assertEqual(result[0][1], "frame")

    def test_close_wakes_consumer_and_rejects_later_frames(self):
        slot = LatestFrame()
        result = []
        t = threading.Thread(target=lambda: result.append(slot.wait(timeout=10)))
        t.start()
        slot.close()
        t.join(1)
        self.assertFalse(t.is_alive())
        self.assertEqual(result, [None])
        slot.put("late")
        self.assertIsNone(slot.peek())


if __name__ == "__main__":
    unittest.main()

import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import av
import numpy as np
from camera_crop import crop_rect, crop_frame, crop_denominator, area_percent, LiveCropSelection
from video_pixels import uyvy_view

class CropTests(unittest.TestCase):
    def test_geometry_and_area(self):
        for width, height in [(1280,720), (1920,1080), (640,480)]:
            for n in range(1,6):
                x,y,w,h = crop_rect(width,height,100/n)
                self.assertEqual(2*x+w,width)
                self.assertEqual(2*y+h,height)
                self.assertEqual(w*height,h*width)
                self.assertEqual(x%2,0)
                self.assertLess(abs(w*h/(width*height)-1/n),.015)

    def test_pixels_and_conversion(self):
        frame = av.VideoFrame(1280,720,'uyvy422')
        pixels = uyvy_view(frame)
        pixels[:] = np.random.default_rng(17).integers(0,256,pixels.shape,dtype=np.uint8)
        for n in range(1,6):
            cropped,(x,y,w,h) = crop_frame(frame,100/n)
            np.testing.assert_array_equal(uyvy_view(cropped), pixels[y:y+h,x:x+w])
            out = cropped.reformat(width=1280,height=720,format='nv12')
            self.assertEqual((out.width,out.height),(1280,720))
            if n == 1: self.assertIs(cropped,frame)

    def test_invalid_defaults(self):
        for value in [None,True,0,6,'2',2.5]:
            self.assertEqual(crop_denominator(value),1)

    def test_continuous_area_and_migration(self):
        self.assertAlmostEqual(area_percent({"crop_area_denominator":3}),100/3)
        self.assertEqual(area_percent({"crop_area_percent":42.7,"crop_area_denominator":4}),42.7)
        for value in [None,True,"50",float("nan"),float("inf")]:
            self.assertEqual(area_percent({"crop_area_percent":value}),100)
        last = 0
        for percent in np.linspace(20,100,801):
            x,y,w,h = crop_rect(1280,720,float(percent))
            self.assertEqual(w*720,h*1280)
            self.assertEqual(2*x+w,1280)
            self.assertEqual(2*y+h,720)
            self.assertGreaterEqual(w*h,last)
            self.assertLess(abs(w*h/(1280*720)-percent/100),.026)
            last = w*h

    def test_live_selection_keeps_last_good_value(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json'
            selection=LiveCropSelection(p,{})
            p.write_text('{"crop_area_percent":42.7}')
            with patch('camera_crop.time.monotonic',return_value=1):
                self.assertEqual(selection.read(),42.7)
            p.write_text('broken')
            with patch('camera_crop.time.monotonic',return_value=2):
                self.assertEqual(selection.read(),42.7)
            p.write_text('{"crop_area_percent":25}')
            with patch('camera_crop.time.monotonic',return_value=3):
                self.assertEqual(selection.read(),25)

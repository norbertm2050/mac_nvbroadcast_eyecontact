import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import av
import numpy as np
from camera_crop import crop_rect, crop_frame, crop_denominator
from video_pixels import uyvy_view

class CropTests(unittest.TestCase):
    def test_geometry_and_area(self):
        for width, height in [(1280,720), (1920,1080), (640,480)]:
            for n in range(1,6):
                x,y,w,h = crop_rect(width,height,n)
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
            cropped,(x,y,w,h) = crop_frame(frame,n)
            np.testing.assert_array_equal(uyvy_view(cropped), pixels[y:y+h,x:x+w])
            out = cropped.reformat(width=1280,height=720,format='nv12')
            self.assertEqual((out.width,out.height),(1280,720))
            if n == 1: self.assertIs(cropped,frame)

    def test_invalid_defaults(self):
        for value in [None,True,0,6,'2',2.5]:
            self.assertEqual(crop_denominator(value),1)

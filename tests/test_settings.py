import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from settings import valid_host, rtsp_url, safe_error, load_config, save_config


class SettingsTests(unittest.TestCase):
    def test_switching_from_ghaust_restores_output_dimensions(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, EYE_CONTACT_DATA_DIR=folder), patch('settings.sys.platform', 'darwin'):
            config = dict(virtual_backend='ghaust', output_width=1920, output_height=1080)
            save_config(config)
            self.assertEqual(load_config()['output_width'], 1920)
            config['virtual_backend'] = 'obs'
            save_config(config)
            result = load_config()
            self.assertEqual((result['output_width'], result['output_height'], result['virtual_pixel_format']), (1280, 720, 'yuv420p'))

    def test_decoder_default_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, EYE_CONTACT_DATA_DIR=folder):
            with patch('settings.sys.platform', 'darwin'):
                self.assertEqual(load_config()['decode_acceleration'], 'software')
                save_config({'decode_acceleration': 'videotoolbox'})
                self.assertEqual(load_config()['decode_acceleration'], 'videotoolbox')
            Path(folder, 'config.json').unlink()
            with patch('settings.sys.platform', 'win32'):
                self.assertEqual(load_config()['decode_acceleration'], 'd3d11va')

    def test_accept_ip_dns_ipv6(self):
        for host in ["192.0.2.10", "windows.example.ts.net", "2001:db8::1"]:
            self.assertEqual(valid_host(host), host)
        self.assertIn(
            "@[2001:db8::1]:8554/raw",
            rtsp_url(dict(host="2001:db8::1", token="a" * 32), "raw"),
        )

    def test_reject_urls_and_injection(self):
        for host in [
            "rtsp://host",
            "host/path",
            "host@evil",
            "host:8554",
            "x\ny",
            "a..b",
            "-bad",
        ]:
            with self.assertRaises(ValueError):
                valid_host(host)

    def test_error_redacts_credentials(self):
        self.assertEqual(
            safe_error("Failed rtsp://eye:secret@host:8554/raw"),
            "Failed rtsp://[redacted]@host:8554/raw",
        )

    def test_private_config_and_fixed_video_format(self):
        with tempfile.TemporaryDirectory() as directory:
            old = os.environ.get("EYE_CONTACT_DATA_DIR")
            os.environ["EYE_CONTACT_DATA_DIR"] = directory
            try:
                save_config(dict(host="192.0.2.10", token="b" * 32, width=1920, fps=60))
                config = load_config()
                self.assertEqual(
                    (config["width"], config["height"], config["fps"]), (1280, 720, 30)
                )
                self.assertEqual(config["token"], "b" * 32)
                if sys.platform != "win32":
                    self.assertEqual(
                        (Path(directory) / "config.json").stat().st_mode & 0o777, 0o600
                    )
            finally:
                if old is None:
                    os.environ.pop("EYE_CONTACT_DATA_DIR", None)
                else:
                    os.environ["EYE_CONTACT_DATA_DIR"] = old


if __name__ == "__main__":
    unittest.main()

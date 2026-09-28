import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import windows_startup as startup


class StartupTests(unittest.TestCase):
    def test_command_quotes_executable_and_requests_service_and_minimize(self):
        command = startup.startup_command(
            r"C:\Program Files\Remote Eye Contact\RemoteEyeContact.exe"
        )
        self.assertEqual(
            command,
            '"C:\\Program Files\\Remote Eye Contact\\RemoteEyeContact.exe" --autostart --minimized',
        )

    def test_missing_broadcast_is_actionable(self):
        with patch.object(
            startup,
            "broadcast_path",
            return_value=Path("/not-an-installed-broadcast.exe"),
        ):
            self.assertIn("未安装", startup.ensure_broadcast())

    def test_existing_broadcast_is_not_relaunched(self):
        path = MagicMock()
        path.exists.return_value = True
        result = MagicMock(returncode=0)
        with (
            patch.object(startup, "broadcast_path", return_value=path),
            patch.object(startup.subprocess, "run", return_value=result),
            patch.object(startup.subprocess, "Popen") as popen,
        ):
            self.assertIsNone(startup.ensure_broadcast())
            popen.assert_not_called()

    def test_missing_process_is_started_hidden(self):
        path = MagicMock()
        path.exists.return_value = True
        result = MagicMock(returncode=1)
        with (
            patch.object(startup, "broadcast_path", return_value=path),
            patch.object(startup.subprocess, "run", return_value=result),
            patch.object(startup.subprocess, "Popen") as popen,
        ):
            self.assertIsNone(startup.ensure_broadcast())
            self.assertIn("--launch-hidden", popen.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

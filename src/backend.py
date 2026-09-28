"""Frozen entry point. GUI and video workers share one bundled runtime."""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--role",
        choices=["mac", "receiver", "sender", "windows"],
        default="windows" if sys.platform == "win32" else "mac",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument("--minimized", action="store_true")
    args = parser.parse_args()
    for name in (
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ):
        os.environ.pop(name, None)
    if args.self_test:
        import av, numpy, pyvirtualcam

        result = f"PyAV {av.__version__}; NumPy {numpy.__version__}; virtual camera backend loaded"
        if sys.stdout:
            print(result)
        return
    if args.role == "mac":
        import mac_camera

        mac_camera.main()
    elif args.role == "receiver":
        import win_receiver
    elif args.role == "sender":
        import win_sender
    else:
        import windows_app

        windows_app.main(autostart=args.autostart, minimized=args.minimized)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        from settings import data_dir, safe_error

        (data_dir() / "logs" / "backend-error.log").write_text(
            safe_error(traceback.format_exc()), encoding="utf-8"
        )
        os._exit(1)

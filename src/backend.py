"""Frozen entry point. GUI and video workers share one bundled runtime."""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--role",
        choices=["mac", "receiver", "sender", "windows", "broadcast"],
        default="windows" if sys.platform == "win32" else "mac",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--action", choices=["status", "prepare", "restore-live"], default="status")
    parser.add_argument("--result", help="JSON result path for headless Broadcast control")
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
    if args.role == "broadcast":
        import json
        import time
        from pathlib import Path
        from settings import atomic_json, data_dir, safe_error
        from broadcast_control import control
        output = Path(args.result) if args.result else data_dir() / "state/broadcast-command.json"
        try:
            result = dict(ok=True, updated=time.time(), result=control(args.action))
        except Exception as error:
            result = dict(ok=False, updated=time.time(), error=safe_error(error))
        atomic_json(output, result)
        if sys.stdout:
            print(json.dumps(result))
        return
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

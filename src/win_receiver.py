"""Video-only RTSP to OBS virtual camera, latest-frame only, interactive session."""

import av, numpy as np, pyvirtualcam, threading, time, json, os, traceback
from pathlib import Path
from video_decode import decode_from_keyframe
from latest_frame import LatestFrame
from av.codec.hwaccel import HWAccel
from settings import data_dir, load_config, safe_error

ROOT = data_dir()
CONFIG = load_config()
latest = LatestFrame()
frames = 0
error = None
actual_accel = "starting"
hardware_failed = False


def receive():
    global frames, error, actual_accel, hardware_failed
    while not (ROOT / "state/stop").exists():
        try:
            accel = (
                "software"
                if hardware_failed
                else CONFIG.get("decode_acceleration", "software")
            )
            hw = (
                HWAccel(accel, allow_software_fallback=True)
                if accel != "software"
                else None
            )
            with av.open(
                f"rtsp://127.0.0.1:{CONFIG['port']}/raw",
                options={
                    "rtsp_transport": "tcp",
                    "fflags": "nobuffer",
                    "flags": "low_delay",
                    "probesize": "32",
                    "analyzeduration": "0",
                    "max_delay": "0",
                    "reorder_queue_size": "0",
                },
                timeout=(4, 4),
                hwaccel=hw,
            ) as stream:
                video = stream.streams.video[0]
                video.codec_context.thread_count = 1
                for frame in decode_from_keyframe(stream, video):
                    actual_accel = (
                        accel if video.codec_context.is_hwaccel else "software"
                    )
                    latest.put(
                        frame.reformat(
                            width=1280, height=720, format="nv12"
                        ).to_ndarray()
                    )
                    frames += 1
                    error = None
        except Exception as e:
            if accel != "software" and (
                "avcodec_" in safe_error(e)
                or "av_hwdevice" in safe_error(e)
                or "hardware" in safe_error(e).lower()
            ):
                hardware_failed = True
            error = safe_error(e)
            time.sleep(1)


try:
    threading.Thread(target=receive, daemon=True).start()
    blank = np.full((720 * 3 // 2, 1280), 128, np.uint8)
    blank[:720] = 16
    last = 0
    last_frames = 0
    last_item = 0
    frame_driven = CONFIG.get("frame_driven_output", False)
    with pyvirtualcam.Camera(
        width=1280, height=720, fps=30, fmt=pyvirtualcam.PixelFormat.NV12, backend="obs"
    ) as cam:
        while not (ROOT / "state/stop").exists():
            item = (
                latest.wait(last_item, timeout=1 / 30)
                if frame_driven
                else latest.peek()
            )
            if item is None:
                item = latest.peek()
            new_frame = item is not None and item[0] != last_item
            now = time.monotonic()
            fresh = item is not None and now - item[0] < 0.4
            if not frame_driven or new_frame or not fresh:
                cam.send(item[1] if fresh else blank)
            if item:
                last_item = item[0]
            if not frame_driven:
                cam.sleep_until_next_frame()
            if now - last > 1:
                try:
                    tmp = ROOT / "logs/native-receiver.tmp"
                    tmp.write_text(
                        json.dumps(
                            dict(
                                pid=os.getpid(),
                                frames=frames,
                                decodeAcceleration=actual_accel,
                                hardwareFallback=hardware_failed,
                                fps=round((frames - last_frames) / (now - last), 2),
                                updated=time.time(),
                                error=error,
                                fresh=bool(item and now - item[0] < 0.4),
                            )
                        )
                    )
                    tmp.replace(ROOT / "logs/native-receiver.json")
                except OSError:
                    pass
                last = now
                last_frames = frames
except Exception:
    (ROOT / "logs/native-receiver-error.txt").write_text(traceback.format_exc())
    raise

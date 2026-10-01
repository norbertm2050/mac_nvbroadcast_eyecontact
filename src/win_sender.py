"""Direct Broadcast DirectShow capture -> low-delay NVENC -> video-only RTSP."""

import av, threading, time, json, os, fractions, traceback
from pathlib import Path
from latest_frame import LatestFrame
from settings import data_dir, load_config, safe_error
from capture_readiness import CaptureReadiness, receiver_is_live

ROOT = data_dir()
CONFIG = load_config()
latest = LatestFrame()
status = {"captured": 0, "sent": 0, "pid": os.getpid()}
input_ready = threading.Event()


def watch_input():
    readiness = CaptureReadiness()
    while not (ROOT / "state/stop").exists():
        ready = readiness.update(
            receiver_is_live(ROOT / "logs/native-receiver.json"), time.monotonic()
        )
        if ready:
            input_ready.set()
        else:
            input_ready.clear()
            status.pop("captureOpened", None)
        status["waitingForInput"] = not ready
        time.sleep(0.5)


def capture():
    while not (ROOT / "state/stop").exists():
        if not input_ready.wait(0.5):
            continue
        try:
            status["captureOpened"] = time.time()
            with av.open(
                "video=Camera (NVIDIA Broadcast)",
                format="dshow",
                options={
                    "video_size": "1280x720",
                    "framerate": "30",
                    "rtbufsize": "4000000",
                },
            ) as camera:
                for frame in camera.decode(video=0):
                    if not input_ready.is_set() or (ROOT / "state/stop").exists():
                        break
                    latest.put(frame)
                    status["captured"] += 1
                    status["lastCapture"] = time.time()
                    status["captureError"] = None
        except Exception as e:
            status["captureError"] = safe_error(e)
            time.sleep(1)


def monitor():
    previous = time.monotonic()
    last = 0
    while not (ROOT / "state/stop").exists():
        now = time.monotonic()
        status["fps"] = round((status["sent"] - last) / max(0.001, now - previous), 2)
        last = status["sent"]
        previous = now
        try:
            tmp = ROOT / "logs/native-sender.tmp"
            tmp.write_text(json.dumps(dict(status, updated=time.time())))
            tmp.replace(ROOT / "logs/native-sender.json")
        except OSError:
            pass
        last_progress = max(status.get("lastCapture", 0), status.get("captureOpened", 0))
        if input_ready.is_set() and status.get("captureOpened") and time.time() - last_progress > 10:
            os._exit(2)
        time.sleep(1)


threading.Thread(target=watch_input, daemon=True).start()
threading.Thread(target=capture, daemon=True).start()
threading.Thread(target=monitor, daemon=True).start()
while not (ROOT / "state/stop").exists():
    try:
        with av.open(
            f"rtsp://127.0.0.1:{CONFIG['port']}/processed",
            "w",
            format="rtsp",
            options={"rtsp_transport": "tcp", "flush_packets": "1"},
            timeout=(5, 5),
        ) as output:
            stream = output.add_stream("h264_nvenc", rate=30)
            stream.width = 1280
            stream.height = 720
            stream.pix_fmt = "nv12"
            stream.bit_rate = 6000000
            stream.codec_context.max_b_frames = 0
            stream.codec_context.gop_size = 30
            stream.codec_context.time_base = fractions.Fraction(1, 30)
            stream.options = {
                "preset": "p2",
                "tune": "ull",
                "zerolatency": "1",
                "delay": "0",
                "bf": "0",
                "rc": "cbr",
                "rc-lookahead": "0",
            }
            last = 0
            pts = 0
            while not (ROOT / "state/stop").exists():
                item = latest.wait(last, timeout=1)
                if item is None:
                    continue
                last, frame = item
                if not input_ready.is_set() or time.monotonic() - last > 0.5:
                    continue
                frame = frame.reformat(format="nv12")
                frame.pict_type = av.video.frame.PictureType.NONE
                frame.pts = pts
                frame.time_base = fractions.Fraction(1, 30)
                pts += 1
                for packet in stream.encode(frame):
                    output.mux(packet)
                status["sent"] += 1
                status["lastSent"] = time.time()
                status["senderError"] = None
    except Exception as e:
        status["senderError"] = safe_error(e)
        time.sleep(1)

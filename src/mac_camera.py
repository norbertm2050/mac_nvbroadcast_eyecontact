#!/usr/bin/env python3
"""Headless camera -> real-time VideoToolbox RTSP -> Broadcast -> direct CMIO sink.

One newest-frame slot per stage: no frame queue can grow while a consumer stalls.
The menu app owns camera permission; neither machine runs the OBS application.
"""

import collections
import fractions
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time
import traceback
import fcntl
import av
import numpy as np
import pyvirtualcam
from settings import data_dir, load_config, rtsp_url, safe_error

ROOT = data_dir()
from latest_frame import LatestFrame
from video_pixels import uyvy_view
from video_codec import mac_encoder_options
from video_decode import decode_from_keyframe
from network_ready import watch_network
from av.codec.hwaccel import HWAccel

import ctypes

cmio = ctypes.CDLL("/System/Library/Frameworks/CoreMediaIO.framework/CoreMediaIO")
address = (ctypes.c_uint32 * 3)(
    int.from_bytes(b"yes ", "big"), int.from_bytes(b"glob", "big"), 0
)
allow = ctypes.c_uint32(1)
cmio.CMIOObjectSetPropertyData(
    1, ctypes.byref(address), 0, None, 4, ctypes.byref(allow)
)

CONFIG = load_config()
STOP = threading.Event()
STATE = {
    "phase": "starting",
    "captureFrames": 0,
    "sentFrames": 0,
    "encodedPackets": 0,
    "receivedFrames": 0,
    "virtualFrames": 0,
    "reconnects": 0,
}
LOCK = threading.Lock()
LATEST = {key: LatestFrame() for key in ["capture", "return"]}
START = time.monotonic()


def state(**values):
    with LOCK:
        STATE.update(values)


def note(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


def put(key, value):
    LATEST[key].put(value)


def get(key):
    return LATEST[key].peek()


def bump(key):
    with LOCK:
        STATE[key] = STATE.get(key, 0) + 1


def capture():
    while not STOP.is_set():
        try:
            opts = {
                "video_size": f"{CONFIG['width']}x{CONFIG['height']}",
                "framerate": str(CONFIG["fps"]),
                "pixel_format": "nv12",
            }
            with av.open(
                CONFIG["camera"] + ":none", format="avfoundation", options=opts
            ) as device:
                state(cameraOpen=True, captureError=None)
                last_capture = 0
                while not STOP.is_set():
                    try:
                        for packet in device.demux(video=0):
                            for frame in packet.decode():
                                if STOP.is_set():
                                    return
                                put("capture", frame)
                                bump("captureFrames")
                                last_capture = time.monotonic()
                    except av.error.BlockingIOError:
                        # AVFoundation is nonblocking; EAGAIN means wait for the next frame.
                        # Sleep through the quiet part of a 30 Hz capture cycle.
                        STOP.wait(
                            max(
                                0.001,
                                min(
                                    0.020,
                                    1 / CONFIG["fps"]
                                    - (time.monotonic() - last_capture)
                                    - 0.002,
                                ),
                            )
                        )
        except Exception as e:
            state(cameraOpen=False, captureError=safe_error(e))
            note("Capture: " + safe_error(e))
            STOP.wait(2)


def sender():
    url = rtsp_url(CONFIG, "raw")
    while not STOP.is_set():
        try:
            with av.open(
                url,
                "w",
                format="rtsp",
                options={"rtsp_transport": "tcp", "flush_packets": "1"},
                timeout=(5, 5),
            ) as output:
                stream = output.add_stream("h264_videotoolbox", rate=CONFIG["fps"])
                stream.width = CONFIG["width"]
                stream.height = CONFIG["height"]
                stream.pix_fmt = "nv12"
                stream.bit_rate = CONFIG["bitrate"]
                stream.codec_context.max_b_frames = 0
                stream.codec_context.gop_size = CONFIG["fps"]
                stream.codec_context.time_base = fractions.Fraction(1, CONFIG["fps"])
                stream.options = mac_encoder_options()
                last = 0
                pts = 0
                while not STOP.is_set():
                    item = LATEST["capture"].wait(last, timeout=0.25)
                    if item is None:
                        continue
                    last, frame = item
                    if CONFIG.get("diagnostic_timestamp"):
                        data = frame.to_ndarray(format="rgb24")
                        stamp = int(time.time() * 1000) % (1 << 24)
                        bits = [1, 0] + [(stamp >> (23 - i)) & 1 for i in range(24)]
                        for i, b in enumerate(bits):
                            data[:20, i * 12 : (i + 1) * 12] = 255 if b else 0
                        frame = av.VideoFrame.from_ndarray(data, format="rgb24")
                    frame = frame.reformat(
                        width=CONFIG["width"], height=CONFIG["height"], format="nv12"
                    )
                    frame.pict_type = av.video.frame.PictureType.NONE
                    frame.pts = pts
                    frame.time_base = fractions.Fraction(1, CONFIG["fps"])
                    pts += 1
                    for packet in stream.encode(frame):
                        output.mux(packet)
                        bump("encodedPackets")
                    bump("sentFrames")
                    state(
                        senderConnected=True,
                        senderError=None,
                        lastSent=time.monotonic(),
                    )
        except Exception as e:
            state(senderConnected=False, senderError=safe_error(e))
            bump("reconnects")
            note("Publish reconnect: " + safe_error(e))
            STOP.wait(1)


def receiver():
    url = rtsp_url(CONFIG, "processed")
    hardware_failed = False
    while not STOP.is_set():
        try:
            options = {
                "rtsp_transport": "tcp",
                "fflags": "nobuffer",
                "flags": "low_delay",
                "probesize": "32",
                "analyzeduration": "0",
                "max_delay": "0",
                "reorder_queue_size": "0",
            }
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
            with av.open(url, options=options, timeout=(4, 4), hwaccel=hw) as container:
                stream = container.streams.video[0]
                stream.codec_context.thread_count = 1
                state(receiverConnected=True, receiverError=None)
                for frame in decode_from_keyframe(container, stream):
                    if STOP.is_set():
                        break
                    fmt = CONFIG.get("virtual_pixel_format", "yuv420p")
                    converted = frame.reformat(
                        width=CONFIG["width"], height=CONFIG["height"], format=fmt
                    )
                    data = (
                        uyvy_view(converted)
                        if fmt == "uyvy422"
                        else converted.to_ndarray()
                    )
                    state(
                        decodeAcceleration=accel
                        if stream.codec_context.is_hwaccel
                        else "software",
                        virtualPixelFormat=fmt,
                    )
                    put("return", data)
                    bump("receivedFrames")
                    if CONFIG.get("diagnostic_timestamp"):
                        # Read luma directly in YUV formats; no diagnostic RGB conversion.
                        row = data[8]
                        if fmt == "uyvy422":
                            bright = lambda x: float(row[x, 1])
                        elif fmt in ["yuv420p", "nv12"]:
                            bright = lambda x: float(row[x])
                        else:
                            bright = lambda x: float(np.mean(row[x]))
                        if bright(6) > 200 and bright(18) < 60:
                            stamp = 0
                            for i in range(24):
                                stamp = stamp * 2 + int(bright((i + 2) * 12 + 6) > 128)
                            age = (int(time.time() * 1000) - stamp) % (1 << 24)
                            if age < 5000:
                                with (ROOT / "logs/native-latency.jsonl").open(
                                    "a"
                                ) as f:
                                    f.write(
                                        json.dumps(
                                            {
                                                "time": time.time(),
                                                "ageMs": age,
                                                "elapsed": time.monotonic() - START,
                                            }
                                        )
                                        + "\n"
                                    )
        except Exception as e:
            if accel != "software" and (
                "avcodec_" in safe_error(e)
                or "av_hwdevice" in safe_error(e)
                or "hardware" in safe_error(e).lower()
            ):
                hardware_failed = True
                state(decoderFallback=safe_error(e))
            state(receiverConnected=False, receiverError=safe_error(e))
            bump("reconnects")
            note("Receive reconnect: " + safe_error(e))
            STOP.wait(1)


def virtual_camera():
    history = collections.deque()
    last = 0
    ready_since = None
    frame_driven = CONFIG.get("frame_driven_output", False)
    fmt = CONFIG.get("virtual_pixel_format", "yuv420p")
    if fmt == "uyvy422":
        blank = np.empty((CONFIG["height"], CONFIG["width"], 2), np.uint8)
        blank[:, :, 0] = 128
        blank[:, :, 1] = 16
        pixel_format = pyvirtualcam.PixelFormat.UYVY
    elif fmt in ["yuv420p", "nv12"]:
        blank = np.full((CONFIG["height"] * 3 // 2, CONFIG["width"]), 128, np.uint8)
        blank[: CONFIG["height"]] = 16
        pixel_format = (
            pyvirtualcam.PixelFormat.I420
            if fmt == "yuv420p"
            else pyvirtualcam.PixelFormat.NV12
        )
    else:
        blank = np.zeros((CONFIG["height"], CONFIG["width"], 3), np.uint8)
        pixel_format = pyvirtualcam.PixelFormat.RGB
    with pyvirtualcam.Camera(
        width=CONFIG["width"],
        height=CONFIG["height"],
        fps=CONFIG["fps"],
        fmt=pixel_format,
        backend="obs",
    ) as cam:
        state(virtualCamera=cam.device, phase="warming")
        while not STOP.is_set():
            item = (
                LATEST["return"].wait(last, timeout=1 / CONFIG["fps"])
                if frame_driven
                else get("return")
            )
            if item is None:
                item = get("return")
            new_frame = item is not None and item[0] != last
            now = time.monotonic()
            if item and item[0] != last:
                last = item[0]
                history.append(now)
            while history and history[0] < now - 2:
                history.popleft()
            captured = get("capture")
            fresh = (
                item is not None
                and now - item[0] < 0.35
                and captured is not None
                and now - captured[0] < 0.35
                and STATE.get("senderConnected", False)
                and now - STATE.get("lastSent", 0) < 0.35
            )
            flowing = fresh and len(history) >= CONFIG["fps"] * 1.4
            if flowing:
                if ready_since is None:
                    ready_since = now
            else:
                ready_since = None
            warmed = (
                ready_since is not None
                and now - ready_since >= CONFIG["warmup_seconds"]
            )
            if warmed:
                # The stream is already 30 fps. Forward each newest frame at arrival,
                # avoiding another independently phased 30 Hz software timer.
                if frame_driven and not new_frame:
                    continue
                cam.send(item[1])
                state(phase="ready", returnAgeMs=round((now - item[0]) * 1000, 1))
            else:
                cam.send(blank)
                state(phase="warming" if fresh else "reconnecting")
            bump("virtualFrames")
            if not frame_driven:
                cam.sleep_until_next_frame()


def monitor():
    before = {}
    previous = time.monotonic()
    while not STOP.wait(1):
        now = time.monotonic()
        with LOCK:
            snapshot = dict(STATE)
            for key in [
                "captureFrames",
                "sentFrames",
                "encodedPackets",
                "receivedFrames",
                "virtualFrames",
            ]:
                snapshot[key.replace("Frames", "Fps").replace("Packets", "Fps")] = (
                    round(
                        (snapshot[key] - before.get(key, snapshot[key]))
                        / (now - previous),
                        1,
                    )
                )
            before = dict(STATE)
        snapshot.update(
            pid=os.getpid(),
            updated=time.time(),
            uptime=round(now - START, 1),
            resolution=[CONFIG["width"], CONFIG["height"]],
            fps=CONFIG["fps"],
            bitrate=CONFIG["bitrate"],
        )
        tmp = ROOT / "state/native-status.tmp"
        tmp.write_text(json.dumps(snapshot, indent=2))
        tmp.replace(ROOT / "state/native-status.json")
        previous = now


def main():
    lock = (ROOT / "state/native.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        note("Already running")
        return
    (ROOT / "state/native.pid").write_text(str(os.getpid()))
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda *_: STOP.set())
    threading.Thread(target=monitor, daemon=True).start()
    try:
        state(phase="connecting")
        rtsp_url(CONFIG, "raw")
        threading.Thread(
            target=watch_network,
            args=(CONFIG["host"], STOP, lambda: STATE.get("phase") == "ready",
                  lambda message: state(networkMessage=message)),
            daemon=True,
        ).start()
        for worker in [capture, sender, receiver]:
            threading.Thread(target=worker, daemon=True).start()
        virtual_camera()
    except Exception as e:
        state(phase="error", error=safe_error(e))
        note(safe_error(traceback.format_exc()))
        (ROOT / "state/native-status.json").write_text(
            json.dumps(dict(STATE, updated=time.time()), indent=2)
        )
    finally:
        STOP.set()
        for slot in LATEST.values():
            slot.close()
        (ROOT / "state/native.pid").unlink(missing_ok=True)
        # Capture driver reads are blocking; process exit releases AVFoundation safely.
        note("Native camera stopped")
        if STATE["phase"] != "error":
            (ROOT / "state/native-status.json").write_text(
                json.dumps({"phase": "stopped", "updated": time.time()})
            )
        os._exit(1 if STATE["phase"] == "error" else 0)


if __name__ == "__main__":
    main()

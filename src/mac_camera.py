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
import resource
import signal
import threading
import time
import traceback
import fcntl
import av
from av.video.reformatter import VideoReformatter
import numpy as np
import pyvirtualcam
from settings import data_dir, load_config, rtsp_url, safe_error
from camera_crop import LiveCropSelection, crop_frame

ROOT = data_dir()
from latest_frame import LatestFrame
from video_pixels import uyvy_view
from video_codec import mac_encoder_options
from resilient_decode import decode_resilient
from mac_runtime import VideoActivity
from video_diagnostics import VideoDiagnostics
from picture_health import PictureHealth
from network_ready import watch_network
from video_readiness import VideoReadiness

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
DIAGNOSTICS = VideoDiagnostics()


def state(**values):
    with LOCK:
        STATE.update(values)


def note(message):
    DIAGNOSTICS.event("message", text=safe_error(message))
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def put(key, value):
    LATEST[key].put(value)


def get(key):
    return LATEST[key].peek()


def bump(key):
    with LOCK:
        STATE[key] = STATE.get(key, 0) + 1


def capture():
    capture_fps = CONFIG["fps"]
    while not STOP.is_set():
        try:
            opts = {
                "video_size": f"{CONFIG['width']}x{CONFIG['height']}",
                "framerate": str(capture_fps),
                "pixel_format": CONFIG.get("capture_pixel_format", "uyvy422"),
            }
            with av.open(
                CONFIG["camera"] + ":none", format="avfoundation", options=opts
            ) as device:
                state(cameraOpen=True, captureError=None, captureFpsRequested=capture_fps)
                next_capture = 0.0
                last_capture = 0
                while not STOP.is_set():
                    try:
                        packets = iter(device.demux(video=0))
                        while not STOP.is_set():
                            with DIAGNOSTICS.span("captureRead"):
                                packet = next(packets)
                            for frame in packet.decode():
                                if STOP.is_set():
                                    return
                                state(capturePixelFormat=frame.format.name,
                                      captureSize=[frame.width, frame.height],
                                      capturePlaneStrides=[p.line_size for p in frame.planes])
                                now = time.monotonic()
                                if now + 0.002 < next_capture:
                                    continue
                                next_capture = max(next_capture + 1 / CONFIG["fps"], now + 0.5 / CONFIG["fps"])
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
            capture_fps = 30
            state(cameraOpen=False, captureError=safe_error(e))
            note("Capture: " + safe_error(e))
            STOP.wait(2)


def sender():
    crop_selection = LiveCropSelection(ROOT / "config.json", CONFIG)
    converter = VideoReformatter()
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
                    with DIAGNOSTICS.span("uplinkConvert"):
                        percent = crop_selection.read()
                        frame, rect = crop_frame(frame, percent)
                        state(cropAreaPercent=percent, cropRect=list(rect))
                        frame = converter.reformat(
                            frame, width=CONFIG["width"], height=CONFIG["height"], format="nv12", threads=1
                        )
                    frame.pict_type = av.video.frame.PictureType.NONE
                    frame.pts = pts
                    frame.time_base = fractions.Fraction(1, CONFIG["fps"])
                    pts += 1
                    with DIAGNOSTICS.span("uplinkEncode"):
                        packets = stream.encode(frame)
                    for packet in packets:
                        with DIAGNOSTICS.span("uplinkMux"):
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
    last_luma_sample = 0
    picture_health = PictureHealth()
    converter = VideoReformatter()
    url = rtsp_url(CONFIG, "processed")
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
            accel = CONFIG.get("decode_acceleration", "software")
            def decoder_event(**event):
                clean = {k: safe_error(v) if isinstance(v, str) else v for k, v in event.items()}
                bump("decoderEvents")
                state(decoderEvent=clean)
                note("Decoder: " + json.dumps(clean))

            with av.open(url, options=options, timeout=(4, 4)) as container:
                stream = container.streams.video[0]
                state(receiverConnected=True, receiverError=None)
                for frame, actual_accel in decode_resilient(container, stream, accel, decoder_event, diagnostics=DIAGNOSTICS):
                    if STOP.is_set():
                        break
                    fmt = CONFIG.get("virtual_pixel_format", "yuv420p")
                    with DIAGNOSTICS.span("returnConvert"):
                        converted = converter.reformat(
                            frame, threads=2, width=CONFIG.get("output_width", CONFIG["width"]),
                            height=CONFIG.get("output_height", CONFIG["height"]), format=fmt
                        )
                        data = (
                            uyvy_view(converted)
                            if fmt == "uyvy422"
                            else converted.to_ndarray()
                        )
                    state(
                        decodeAcceleration=actual_accel,
                        virtualPixelFormat=fmt,
                    )
                    if time.monotonic() - last_luma_sample >= 1:
                        sample = data[::32, ::32, :3] if fmt == "bgra" else data[:CONFIG["height"]:32, ::32]
                        state(returnSampleMean=round(float(np.mean(sample)), 2),
                              returnSampleStd=round(float(np.std(sample)), 2),
                              returnUniformBlack=picture_health.update(float(np.mean(sample)), float(np.std(sample)), time.monotonic(), rgb=fmt == "bgra"))
                        last_luma_sample = time.monotonic()
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
            state(receiverConnected=False, receiverError=safe_error(e))
            bump("reconnects")
            note("Receive reconnect: " + safe_error(e))
            STOP.wait(1)


def virtual_camera():
    history = collections.deque()
    last = 0
    readiness = VideoReadiness(CONFIG["warmup_seconds"])
    previous_fresh = None
    previous_output = None
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
    elif fmt == "bgra":
        blank = np.zeros((1080, 1920, 4), np.uint8)
        blank[:, :, 3] = 255
        pixel_format = None  # Direct CMIO backend receives BGRA without pyvirtualcam.
    else:
        blank = np.zeros((CONFIG["height"], CONFIG["width"], 3), np.uint8)
        pixel_format = pyvirtualcam.PixelFormat.RGB
    if CONFIG.get("virtual_backend") == "ghaust":
        from ghaust_camera import Camera
        camera = Camera()
    else:
        camera = pyvirtualcam.Camera(
            width=CONFIG["width"],
            height=CONFIG["height"],
            fps=CONFIG["fps"],
            fmt=pixel_format,
            backend="obs",
        )
    with camera as cam:
        state(virtualCamera=cam.device, phase="warming")
        state(outputResolution=[CONFIG.get("output_width", CONFIG["width"]),
                                CONFIG.get("output_height", CONFIG["height"])])
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
            ages = {
                "return": now - item[0] if item else None,
                "capture": now - captured[0] if captured else None,
                "sender": now - STATE.get("lastSent", 0),
            }
            stale = [key for key, age in ages.items() if age is None or age >= 0.75]
            if not STATE.get("senderConnected", False):
                stale.append("senderDisconnected")
            fresh = not stale
            if fresh != previous_fresh:
                if not fresh:
                    bump("freshnessLosses")
                    detail = {"stages": stale, "ageMs": {
                        key: round(age * 1000, 1) if age is not None else None
                        for key, age in ages.items()}}
                    state(lastFreshnessLoss=detail)
                    note("Video freshness lost: " + json.dumps(detail))
                previous_fresh = fresh
            # At least 15 unique frames/s during warmup. Once ready, only
            # freshness (not a throughput dip) can blank the output.
            flowing = fresh and len(history) >= CONFIG["fps"]
            warmed = readiness.update(fresh, flowing, now)
            if warmed:
                # The stream is already 30 fps. Forward each newest frame at arrival,
                # avoiding another independently phased 30 Hz software timer.
                if frame_driven and not new_frame:
                    continue
                output_kind = "live"
                with DIAGNOSTICS.span("virtualSend"):
                    accepted = cam.send(item[1])
                state(phase="no_picture" if STATE.get("returnUniformBlack") else "ready", returnAgeMs=round((now - item[0]) * 1000, 1))
            else:
                output_kind = "blank"
                with DIAGNOSTICS.span("virtualSend"):
                    accepted = cam.send(blank)
                bump("blankFrames")
                state(phase="warming" if fresh else "reconnecting")
            if accepted is False:
                bump("virtualDroppedFrames")
            else:
                bump("virtualSubmittedFrames")
            state(lastOutputKind=output_kind, outputSubmission="dropped" if accepted is False else "submitted")
            if output_kind != previous_output:
                DIAGNOSTICS.event("output_transition", output=output_kind, staleStages=stale,
                                  ageMs={k: round(v*1000, 1) if v is not None else None for k,v in ages.items()},
                                  fresh=fresh, flowing=flowing)
                previous_output = output_kind
            bump("virtualFrames")
            if not frame_driven:
                cam.sleep_until_next_frame()


def monitor():
    before = {}
    previous_cpu = time.process_time()
    previous = time.monotonic()
    while not STOP.wait(1):
        now = time.monotonic()
        cpu = time.process_time()
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
            processCpuPercent=round((cpu-previous_cpu)/max(now-previous, .001)*100, 1),
            processPeakRssMiB=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576, 1),
        )
        tmp = ROOT / "state/native-status.tmp"
        tmp.write_text(json.dumps(snapshot, indent=2))
        tmp.replace(ROOT / "state/native-status.json")
        try:
            health = {k: v for k, v in snapshot.items() if not k.endswith("Error") and k not in ["error", "networkMessage"]}
            DIAGNOSTICS.write({"kind": "health", "intervalSeconds": round(now-previous, 3),
                               "health": health, "timing": DIAGNOSTICS.snapshot()})
        except Exception as error:
            state(diagnosticsError=safe_error(error))
        previous = now
        previous_cpu = cpu


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
    DIAGNOSTICS.start(ROOT / "logs", CONFIG)
    # Preserve native VideoToolbox/FFmpeg error details without synchronous
    # disk writes from decoder callback threads or authenticated URLs.
    class CodecLogHandler(logging.Handler):
        def emit(self, record):
            DIAGNOSTICS.event("ffmpeg", text=safe_error(record.getMessage()))
    codec_logger = logging.getLogger("libav")
    codec_logger.addHandler(CodecLogHandler())
    codec_logger.setLevel(logging.ERROR)
    codec_logger.propagate = False
    av.logging.set_level(av.logging.ERROR)
    threading.Thread(target=monitor, daemon=True).start()
    activity = None
    try:
        activity = VideoActivity()
        activity.video_thread()
        state(phase="connecting", latencyCriticalActivity=True)
        rtsp_url(CONFIG, "raw")
        threading.Thread(
            target=watch_network,
            args=(CONFIG["host"], STOP, lambda: STATE.get("phase") == "ready",
                  lambda message: state(networkMessage=message)),
            daemon=True,
        ).start()
        def run_video(worker):
            try:
                activity.video_thread()
                worker()
            except Exception as error:
                state(phase="error", error=safe_error(error))
                note("Video worker failed: " + safe_error(error))
                STOP.set()

        for worker in [capture, sender, receiver]:
            threading.Thread(target=run_video, args=(worker,), daemon=True).start()
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
        DIAGNOSTICS.write({"kind": "shutdown", "phase": STATE["phase"], "timing": DIAGNOSTICS.snapshot()})
        DIAGNOSTICS.close()
        if activity is not None:
            activity.close()
        os._exit(1 if STATE["phase"] == "error" else 0)


if __name__ == "__main__":
    main()

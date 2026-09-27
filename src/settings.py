"""Per-user configuration, independent of the executable's location."""

import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote


def data_dir():
    override = os.environ.get("EYE_CONTACT_DATA_DIR")
    if override:
        root = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ["LOCALAPPDATA"]) / "Remote Eye Contact"
    else:
        root = Path.home() / "Library/Application Support/Remote Eye Contact"
    for child in ("state", "logs"):
        (root / child).mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        root.chmod(0o700)
    return root


def valid_host(value):
    value = value.strip()
    if not value or len(value) > 253:
        raise ValueError(
            "请输入 Windows 的 IP 或主机名，不要包含 rtsp://、端口或路径。"
        )
    try:
        ipaddress.ip_address(value.strip("[]"))
        return value.strip("[]")
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
            raise ValueError("地址只能是 IP 或主机名。")
        if any(
            not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
            for label in value.split(".")
        ):
            raise ValueError("无效的主机名。")
        return value


def load_config():
    path = data_dir() / "config.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    defaults = dict(camera="0", host="", port=8554, token="")
    defaults.update(config)
    defaults.update(
        width=1280,
        height=720,
        fps=30,
        bitrate=6000000,
        warmup_seconds=3,
        decode_acceleration="d3d11va" if sys.platform == "win32" else "videotoolbox",
        frame_driven_output=True,
        virtual_pixel_format="yuv420p",
    )
    return defaults


def save_config(config):
    path = data_dir() / "config.json"
    atomic_json(path, config)
    if sys.platform != "win32":
        path.chmod(0o600)


def atomic_json(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def rtsp_url(config, path):
    host = valid_host(config["host"])
    if ":" in host:
        host = "[" + host + "]"
    port = int(config.get("port", 8554))
    if not 1 <= port <= 65535:
        raise ValueError("端口需要在 1–65535 之间。")
    token = config.get("token", "")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", token):
        raise ValueError("请复制 Windows 端显示的 32 位连接码。")
    return f"rtsp://eye:{quote(token, safe='')}@{host}:{port}/{path}"


def safe_error(error):
    # FFmpeg exceptions may include the full authenticated URL.
    return re.sub(r"(rtsp://)[^/@\s]+@", r"\1[redacted]@", str(error))

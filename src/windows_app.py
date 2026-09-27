"""Portable Windows controller. All child processes belong to a kill-on-close job."""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
from settings import atomic_json, data_dir, load_config, save_config

CREATE_NO_WINDOW = 0x08000000
_JOB = None
_MUTEX = None


def own_process_tree():
    """Closing/crashing the UI must never leave camera workers behind."""
    global _JOB, _MUTEX
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    _MUTEX = kernel.CreateMutexW(None, False, "Local\\RemoteEyeContactPortable")
    if not _MUTEX or ctypes.get_last_error() == 183:
        raise RuntimeError("Remote Eye Contact 已在运行。请使用已打开的窗口。")

    class BASIC(ctypes.Structure):
        _fields_ = [
            ("ProcessTime", ctypes.c_int64),
            ("JobTime", ctypes.c_int64),
            ("Flags", wintypes.DWORD),
            ("Min", ctypes.c_size_t),
            ("Max", ctypes.c_size_t),
            ("Count", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("Priority", wintypes.DWORD),
            ("Scheduling", wintypes.DWORD),
        ]

    class IO(ctypes.Structure):
        _fields_ = [
            (n, ctypes.c_uint64)
            for n in (
                "ReadOps",
                "WriteOps",
                "OtherOps",
                "ReadBytes",
                "WriteBytes",
                "OtherBytes",
            )
        ]

    class LIMIT(ctypes.Structure):
        _fields_ = [
            ("Basic", BASIC),
            ("IO", IO),
            ("ProcessMemory", ctypes.c_size_t),
            ("JobMemory", ctypes.c_size_t),
            ("PeakProcess", ctypes.c_size_t),
            ("PeakJob", ctypes.c_size_t),
        ]

    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    _JOB = kernel.CreateJobObjectW(None, None)
    limit = LIMIT()
    limit.Basic.Flags = 0x2000
    if (
        not _JOB
        or not kernel.SetInformationJobObject(
            _JOB, 9, ctypes.byref(limit), ctypes.sizeof(limit)
        )
        or not kernel.AssignProcessToJobObject(_JOB, kernel.GetCurrentProcess())
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def worker_command(role):
    return (
        [sys.executable, "--role", role]
        if getattr(sys, "frozen", False)
        else [
            sys.executable,
            str(Path(__file__).with_name("backend.py")),
            "--role",
            role,
        ]
    )


def media_config(config):
    # JSON is also valid YAML. Only one authenticated remote publisher/reader role.
    return dict(
        logLevel="warn",
        rtsp=True,
        rtspAddress=f":{config['port']}",
        rtspTransports=["tcp"],
        rtmp=False,
        moq=False,
        hls=False,
        webrtc=False,
        srt=False,
        api=False,
        metrics=False,
        pprof=False,
        playback=False,
        writeQueueSize=512,
        udpMaxPayloadSize=1200,
        readTimeout="5s",
        writeTimeout="5s",
        authMethod="internal",
        authInternalUsers=[
            dict(
                user="any",
                ips=["127.0.0.1", "::1"],
                permissions=[
                    dict(action="read", path="raw"),
                    dict(action="publish", path="processed"),
                ],
            ),
            dict(
                user="eye",
                **{"pass": config["token"]},
                ips=[],
                permissions=[
                    dict(action="publish", path="raw"),
                    dict(action="read", path="processed"),
                ],
            ),
        ],
        paths=dict(
            raw=dict(source="publisher", overridePublisher=False),
            processed=dict(source="publisher", overridePublisher=False),
        ),
    )


class Window:
    def __init__(self, root):
        self.root = root
        self.home = data_dir()
        self.config = load_config()
        self.children = {}
        self.handles = {}
        self.running = False
        self.started = 0
        if not self.config.get("token"):
            self.config["token"] = secrets.token_hex(16)
            save_config(self.config)
        root.title("Remote Eye Contact · Windows")
        root.geometry("660x485")
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Remote Eye Contact", font=("Segoe UI", 20, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            frame,
            text="NVIDIA Broadcast 眼神矫正 · 720p / 30 fps",
            padding=(0, 4, 0, 15),
        ).pack(anchor="w")
        ips = sorted(
            {
                x[4][0]
                for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            }
            - {"127.0.0.1"}
        )
        ttk.Label(
            frame, text="Windows 地址（Mac 填写其中一个可达地址，或 Tailscale 主机名）"
        ).pack(anchor="w")
        self.address = tk.StringVar(value="  /  ".join(ips) or socket.gethostname())
        ttk.Entry(frame, textvariable=self.address, state="readonly", width=80).pack(
            fill="x", pady=(3, 12)
        )
        ttk.Label(frame, text="连接码（首次在 Mac 填入；请勿公开分享）").pack(
            anchor="w"
        )
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(3, 12))
        self.code = tk.StringVar(value=self.config["token"])
        ttk.Entry(row, textvariable=self.code, state="readonly", width=45).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(row, text="复制连接码", command=self.copy).pack(
            side="right", padx=(8, 0)
        )
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Label(row, text="RTSP 端口").pack(side="left")
        self.port = tk.StringVar(value=str(self.config["port"]))
        self.port_entry = ttk.Entry(row, textvariable=self.port, width=8)
        self.port_entry.pack(side="left", padx=10)
        ttk.Button(row, text="设置防火墙", command=self.firewall).pack(
            side="left", padx=10
        )
        self.button = ttk.Button(row, text="启动服务", command=self.toggle)
        self.button.pack(side="right")
        self.status = tk.StringVar(
            value="已停止。先在 Broadcast 选择 OBS Virtual Camera，开启 Eye Contact。"
        )
        ttk.Label(
            frame, textvariable=self.status, wraplength=610, padding=(0, 16, 0, 8)
        ).pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="打开 NVIDIA Broadcast", command=self.broadcast).pack(
            side="left"
        )
        ttk.Button(
            row, text="运行日志", command=lambda: os.startfile(self.home / "logs")
        ).pack(side="left", padx=8)
        ttk.Button(
            row,
            text="安装与使用说明",
            command=lambda: webbrowser.open(
                "https://github.com/norbertm2050/mac_nvbroadcast_eyecontact#readme"
            ),
        ).pack(side="left")
        ttk.Label(
            frame,
            text="两端需先安装 OBS 虚拟摄像头驱动；无需运行 OBS。\nWindows 需登录桌面并保持唤醒。仅传输视频，不采集麦克风。",
            wraplength=610,
        ).pack(anchor="w", pady=8)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(1000, self.poll)

    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.code.get())

    def firewall(self):
        try:
            port = int(self.port.get())
            if not 1024 <= port <= 65535:
                raise ValueError("端口需在 1024–65535 之间。")
            script = Path(sys.executable).parent / "configure-firewall.ps1"
            if not script.exists():
                raise RuntimeError("防火墙助手仅包含在完整 Windows 发行包中。")
            args = f'-NoProfile -ExecutionPolicy Bypass -File "{script}" -Port {port}'
            shell = ctypes.WinDLL("shell32", use_last_error=True)
            shell.ShellExecuteW.argtypes = [
                wintypes.HWND,
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                ctypes.c_int,
            ]
            shell.ShellExecuteW.restype = ctypes.c_void_p
            result = shell.ShellExecuteW(None, "runas", "powershell.exe", args, None, 1)
            if not result or result <= 32:
                raise RuntimeError("未完成管理员授权；可以重试或手动配置防火墙。")
        except Exception as e:
            messagebox.showerror("防火墙设置", str(e))

    def broadcast(self):
        path = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            / "NVIDIA Corporation/NVIDIA Broadcast/NVIDIA Broadcast.exe"
        )
        if path.exists():
            os.startfile(path)
        else:
            webbrowser.open(
                "https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-app/"
            )

    def spawn(self, key, command):
        handle = (self.home / "logs" / f"{key}.log").open("ab", buffering=0)
        if key in self.handles:
            self.handles[key].close()
        self.handles[key] = handle
        self.children[key] = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=handle,
            creationflags=CREATE_NO_WINDOW,
        )

    def toggle(self):
        if self.running:
            self.stop()
            return
        try:
            port = int(self.port.get())
            if not 1024 <= port <= 65535:
                raise ValueError("端口需在 1024–65535 之间。")
            with socket.socket() as sock:
                sock.bind(("0.0.0.0", port))
            (self.home / "state/stop").unlink(missing_ok=True)
            self.config["port"] = port
            save_config(self.config)
            binary = (
                Path(sys.executable).parent / "mediamtx.exe"
                if getattr(sys, "frozen", False)
                else Path(__file__).parents[1] / "vendor/mediamtx.exe"
            )
            if not binary.exists():
                raise RuntimeError("缺少 mediamtx.exe，请完整解压 Windows 发行包。")
            atomic_json(self.home / "mediamtx.yml", media_config(self.config))
            for name in ("native-receiver.json", "native-sender.json"):
                (self.home / "logs" / name).unlink(missing_ok=True)
            self.spawn("mediamtx", [str(binary), str(self.home / "mediamtx.yml")])
            self.spawn("receiver", worker_command("receiver"))
            self.spawn("sender", worker_command("sender"))
            self.running = True
            self.started = time.time()
            self.button.configure(text="停止服务")
            self.port_entry.configure(state="disabled")
            self.status.set("正在启动… 请允许防火墙访问所使用的网络。")
        except Exception as e:
            self.stop()
            messagebox.showerror(
                "启动失败", str(e) + "\n若端口被占用，请停止旧服务或更换两端端口。"
            )

    def stop(self):
        (self.home / "state/stop").touch()
        # The virtual-camera writer must close normally before we end readers.
        receiver = self.children.get("receiver")
        if receiver:
            try:
                receiver.wait(timeout=2)
            except subprocess.TimeoutExpired:
                receiver.terminate()
        for p in self.children.values():
            if p.poll() is None:
                p.terminate()
        for p in self.children.values():
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
        self.children.clear()
        for f in self.handles.values():
            f.close()
        self.handles.clear()
        self.running = False
        self.button.configure(text="启动服务")
        self.port_entry.configure(state="normal")
        self.status.set("已停止，摄像头资源已释放。")
        atomic_json(
            self.home / "state/windows-status.json",
            dict(phase="stopped", updated=time.time()),
        )

    def poll(self):
        if self.running:
            rx = {}
            tx = {}
            try:
                rx = json.loads((self.home / "logs/native-receiver.json").read_text())
                tx = json.loads((self.home / "logs/native-sender.json").read_text())
            except (OSError, ValueError):
                pass
            if self.children["mediamtx"].poll() is not None:
                self.stop()
                self.status.set(
                    "视频服务启动失败，请查看 mediamtx.log，确认端口没有被其他程序占用。"
                )
            else:
                for role, stats in [("receiver", rx), ("sender", tx)]:
                    p = self.children[role]
                    if p.poll() is not None or (
                        stats and time.time() - stats.get("updated", 0) > 15
                    ):
                        if p.poll() is None:
                            p.kill()
                            p.wait()
                        self.spawn(role, worker_command(role))
                ready = (
                    bool(rx.get("fresh"))
                    and rx.get("fps", 0) > 22
                    and tx.get("fps", 0) > 22
                    and min(rx.get("updated", 0), tx.get("updated", 0))
                    > time.time() - 5
                )
                self.status.set(
                    f"处理中 · 接收 {rx.get('fps', 0):.0f} fps / 输出 {tx.get('fps', 0):.0f} fps"
                    if ready
                    else "等待 Mac 视频… 若已连接，请检查地址、连接码、防火墙和 Broadcast 设置。"
                )
                atomic_json(
                    self.home / "state/windows-status.json",
                    dict(
                        phase="ready" if ready else "waiting",
                        updated=time.time(),
                        receiveFps=rx.get("fps", 0),
                        sendFps=tx.get("fps", 0),
                    ),
                )
        self.root.after(1000, self.poll)

    def close(self):
        self.stop()
        self.root.destroy()


def main(autostart=False):
    root = tk.Tk()
    try:
        own_process_tree()
    except Exception as e:
        root.withdraw()
        messagebox.showerror("Remote Eye Contact", str(e))
        root.destroy()
        return
    window = Window(root)
    if autostart:
        root.after(500, window.toggle)
    root.mainloop()

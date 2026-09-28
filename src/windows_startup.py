"""User-session startup. Never store a Windows login password in app settings."""

import os
from pathlib import Path
import subprocess
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "RemoteEyeContact"


def startup_command(executable=None):
    executable = executable or sys.executable
    args = [str(executable)]
    if not getattr(sys, "frozen", False) and executable == sys.executable:
        args.append(str(Path(__file__).with_name("backend.py")))
    return subprocess.list2cmdline(args + ["--autostart", "--minimized"])


def enable_startup(enabled):
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass


def startup_enabled():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, RUN_NAME)[0])
    except FileNotFoundError:
        return False


def broadcast_path():
    return (
        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        / "NVIDIA Corporation/NVIDIA Broadcast/NVIDIA Broadcast.exe"
    )


def ensure_broadcast():
    """Start Broadcast only if absent in our interactive session."""
    path = broadcast_path()
    if not path.exists():
        return "未安装 NVIDIA Broadcast，请先安装并配置 Eye Contact。"
    script = "$session=(Get-Process -Id $PID).SessionId; if (Get-Process 'NVIDIA Broadcast' -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $session}) {exit 0} else {exit 1}"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=8,
        creationflags=0x08000000,
    )
    if result.returncode == 1:
        subprocess.Popen(
            [str(path), "--process-start-args", "--launch-hidden"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif result.returncode:
        return "无法检查 NVIDIA Broadcast 状态。"
    return None

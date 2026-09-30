"""Restore an already authenticated Tailscale connection for Tailnet destinations.

No login, preference changes, or network management for ordinary LAN hosts.
Command output can contain account details, so only fixed status messages escape.
"""

import ipaddress
import json
from pathlib import Path
import subprocess


def uses_tailscale(host):
    host = host.strip().strip("[]").lower().rstrip(".")
    if host.endswith(".ts.net"):
        return True
    try:
        address = ipaddress.ip_address(host)
        network = "100.64.0.0/10" if address.version == 4 else "fd7a:115c:a1e0::/48"
        return address in ipaddress.ip_network(network)
    except ValueError:
        return False


def find_cli():
    for path in (
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
    ):
        if Path(path).is_file():
            return path
    return None


def run_command(args, timeout=8):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def ensure_network(host, stop, report):
    if stop.is_set() or not uses_tailscale(host):
        return None
    cli = find_cli()
    if not cli:
        return "此地址需要 Tailscale：请安装并登录，或改用 Windows 局域网 IP"
    try:
        result = run_command([cli, "status", "--json"])
        if result.returncode:
            return "无法检查 Tailscale，请打开 Tailscale 检查连接"
        state = json.loads(result.stdout).get("BackendState")
        if state == "Stopped":
            if stop.is_set():
                return None
            report("正在恢复 Tailscale 连接…")
            result = run_command([cli, "up"], timeout=15)
            if result.returncode:
                return "Tailscale 自动连接失败，请在 Tailscale 中连接"
            result = run_command([cli, "status", "--json"])
            state = json.loads(result.stdout).get("BackendState") if not result.returncode else None
        if state == "Running":
            return None
        if state in ("NeedsLogin", "NeedsMachineAuth", "NoState"):
            return "请在 Tailscale 中完成登录或设备授权"
        return "等待 Tailscale 网络就绪…"
    except subprocess.TimeoutExpired:
        return "Tailscale 连接超时，请检查 Tailscale 状态"
    except (OSError, ValueError):
        return "无法检查 Tailscale，请打开 Tailscale 检查连接"


def watch_network(host, stop, is_ready, report):
    if not uses_tailscale(host):
        return
    while not stop.is_set():
        if is_ready():
            report(None)
        else:
            message = ensure_network(host, stop, report)
            if not stop.is_set():
                report(message)
        stop.wait(20)

#!/usr/bin/env python3
"""Expose the Windows loopback MCP gateway on local loopback through authenticated SSH."""
import argparse
import base64
import hashlib
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', help='SSH user@host')
    parser.add_argument('--identity', help='Optional SSH key path')
    parser.add_argument('--local-port', type=int, default=18100)
    parser.add_argument('--stop', action='store_true', help='Stop the tunnel created by this helper')
    args = parser.parse_args()
    if args.destination.startswith('-') or not 1024 <= args.local_port <= 65535:
        parser.error('Invalid destination or local port')
    # A short path avoids Unix-domain socket length limits on macOS.
    root = Path.home() / '.remote-eye-contact'
    root.mkdir(mode=0o700, exist_ok=True)
    tag = hashlib.sha256(f'{args.destination}:{args.local_port}'.encode()).hexdigest()[:16]
    socket = str(root / ('mcp-' + tag))
    ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
    if args.identity:
        ssh += ['-i', args.identity]
    if args.stop:
        return subprocess.run(ssh + ['-S', socket, '-O', 'exit', args.destination]).returncode
    check = subprocess.run(ssh + ['-S', socket, '-O', 'check', args.destination],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check.returncode == 0:
        print('Tunnel already running; use --stop before refreshing gateway discovery.')
        return 0
    discovery = '''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$p=Join-Path $env:APPDATA 'nvidia-broadcast\\gateway.json'
$j=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((Get-Content -LiteralPath $p -Raw).Trim())) | ConvertFrom-Json
[Console]::WriteLine([int]$j.port)
'''
    encoded = base64.b64encode(discovery.encode('utf-16le')).decode('ascii')
    result = subprocess.run(ssh + [args.destination, 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + encoded],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise SystemExit('Unable to discover the running Windows Broadcast gateway: ' + result.stderr)
    port = int(result.stdout.strip())
    if not 18100 <= port <= 18109:
        raise SystemExit('Invalid Broadcast gateway port')
    command = ssh + ['-M', '-S', socket, '-f', '-N', '-o', 'ExitOnForwardFailure=yes',
                     '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
                     '-L', f'127.0.0.1:{args.local_port}:127.0.0.1:{port}', args.destination]
    subprocess.run(command, check=True, timeout=20)
    print(f'Tunnel started: http://127.0.0.1:{args.local_port}/gateway')
    print('Register this URL in your MCP client and verify server name nvidia-broadcast.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

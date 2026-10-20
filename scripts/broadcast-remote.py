#!/usr/bin/env python3
"""Control a running Windows Broadcast through SSH and the portable app's local MCP client."""
import argparse
import base64
import json
import subprocess
import sys
import uuid


def ps_string(value):
    return "'" + value.replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', help='SSH user@host; configure SSH keys first')
    parser.add_argument('--app', required=True, help='Absolute Windows path to RemoteEyeContact.exe')
    parser.add_argument('--identity', help='Optional local SSH private-key path')
    parser.add_argument('--action', choices=['status', 'prepare', 'restore-live'], default='status')
    args = parser.parse_args()
    if args.destination.startswith('-'):
        parser.error('Invalid SSH destination')
    filename = 'broadcast-command-' + uuid.uuid4().hex + '.json'
    script = f'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$result=Join-Path $env:LOCALAPPDATA {ps_string('Remote Eye Contact/state/' + filename)}
$p=Start-Process -FilePath {ps_string(args.app)} -ArgumentList @('--role','broadcast','--action',{ps_string(args.action)},'--result',('"'+$result+'"')) -Wait -PassThru
if (!(Test-Path -LiteralPath $result)) {{ throw 'Control command produced no result' }}
[Console]::WriteLine([IO.File]::ReadAllText($result))
'''
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
    if args.identity:
        command += ['-i', args.identity]
    command += [args.destination, 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' +
                base64.b64encode(script.encode('utf-16le')).decode('ascii')]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=120)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        return 1
    payload = json.loads(result.stdout.lstrip('\ufeff'))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())

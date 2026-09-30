# Changelog

## 1.1.1 — 2026-09-30

- Mac automatically reconnects an already authenticated but stopped Tailscale connection when the configured Windows address belongs to Tailscale.
- Show actionable network/login status in the menu; retry while video is unavailable without polling Tailscale during healthy streaming. Ordinary LAN addresses do not trigger Tailscale commands.

## 1.1.0 — 2026-09-28

- Enable configurable Windows logon startup with minimized UI and automatic Broadcast launch.
- Retry transient service startup/server failures and keep Windows awake while the service runs; stop cancels retry and releases the sleep request.
- Add an original AI-generated eye/camera app icon to the Mac bundle, Windows executable and window.
- Document the distinction between application startup and Windows automatic login; login credentials are never part of the application or release.

## 1.0.0 — 2026-09-27

- Portable Apple Silicon Mac application and Windows x64 application folder with bundled runtimes.
- Mac menu switches between start and stop; repeated actions are disabled during camera authorization and shutdown.
- User-configured Windows address, port and random connection code; no SSH or personal deployment data in the public project.
- Fixed 720p30, video-only transport with VideoToolbox, D3D11VA and NVENC acceleration and latest-frame forwarding.
- Warmup, reconnect, safe stale-frame output and clean virtual camera shutdown.
- Windows firewall setup helper scoped to local subnets and Tailscale ranges.
- MIT-licensed original source, third-party notices, corresponding dependency source archive and reproducible build instructions.

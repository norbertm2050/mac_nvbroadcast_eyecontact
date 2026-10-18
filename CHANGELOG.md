# Changelog

## Unreleased — 2026-10-18

- Default Mac return decoding to software at 720p after recurrent VideoToolbox decode failures in live tests. Keep hardware encoding and Windows acceleration; allow explicit `decode_acceleration: videotoolbox` opt-in with recovery.

- Recover Mac decoders at keyframes while retaining the RTSP session. Replace permanent software fallback after one decode error with bounded hardware retries, temporary software fallback and non-disruptive hardware probes. Refresh the connection if software decoding repeatedly fails too.
- Record which video stage became stale so intermittent blank output can be diagnosed instead of inferred from frame-rate samples alone.
- Reuse per-worker Mac pixel converters with bounded thread counts instead of creating and destroying automatic scaling thread pools for each frame.
- Declare live video as latency-critical user-initiated work on macOS and set video-worker QoS while streaming. Release the activity on shutdown; do not change global energy settings.

- Add optional direct CMIO sink output for a separately installed GhaustCam 1.0 extension on Mac, including device discovery after renaming. Keep OBS as the default and preserve backend selection when saving connection settings.
- Keep processing and transport at 720p30; upscale only the local GhaustCam output to its advertised 1080p BGRA format. Bound the native queue and pixel-buffer pool to avoid accumulating stale frames.
- Build and bundle the original native adapter; do not redistribute the third-party camera extension.

## Unreleased — 2026-10-01

- Capture Mac camera frames as UYVY before converting to NV12 for hardware encoding, fixing observed striped/corrupted input with direct NV12 capture. Expose capture format, dimensions and plane strides in local health status.
- Preserve ready video across frame-rate dips instead of repeatedly blanking it for warmup. Actual stale video still blanks after 0.75 seconds; recovery uses a shorter warmup.
- Open Broadcast output after live Windows input has warmed up; reopen after sustained input loss. Debounce brief input interruptions to avoid unnecessary camera restarts.

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

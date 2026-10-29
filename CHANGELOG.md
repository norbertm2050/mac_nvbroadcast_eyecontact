# Changelog

## Unreleased — 2026-10-29

- Detect supervisor pauses of 30 seconds or longer as possible sleep/resume events, record them, and reopen disposable Windows receive/capture workers without changing camera format or restarting Windows.

- Recover a confirmed empty Broadcast camera enumeration after three consecutive checks while Mac input is fresh: restart only Broadcast in the current user session and reopen the stale DirectShow sender handle. Bound attempts to two per controller run, at least five minutes apart; do not trigger from generic gateway errors, dark scenes, or active file processing.
- Sample Windows output picture health once per second and stop reporting ready while output is uniformly black or Broadcast configuration has failed. Record recovery attempts and reasons without storing images.

## Unreleased — 2026-10-27

- Add saved Windows device profiles with names, per-device connection credentials, automatic migration of the existing connection, and orderly stop/start switching from the Mac menu.

## Unreleased — 2026-10-25

- Increase crop tick density to every 10%, widen the slider for aligned readable labels, and strengthen magnetic capture to 3.5 percentage points.

- Show native slider ticks and percentage labels at 20% intervals; align magnetic anchors with those visible ticks while retaining free adjustment between them.

- Replace discrete Mac crop choices with a continuous 20–100% area slider, magnetic anchors at the previous choices, live updates throttled to 10 Hz, and migration of saved choices.

- Add persistent live centered camera area cropping (full, 1/2, 1/3, 1/4, 1/5) to the Mac menu. Crop packed YUV before encoding without an RGB round trip, preserve aspect ratio and the 720p output contract, and report the applied rectangle in diagnostics.

## Unreleased — 2026-10-20

- Retain Windows Broadcast capture for up to 20 seconds of input interruption, avoiding unnecessary DirectShow reopen and warmup after transient Mac stalls. Stale-input blanking is unchanged. Keep capture-handle lifetime status accurate and expose capture-open counts.

- Integrate the Broadcast 2.3 local MCP gateway for idempotent OBS 720p30 and Eye Contact configuration, with live capability checks and explicit file-processing conflict handling.
- Add authenticated SSH remote status, prepare and restore-live commands using the portable Windows executable, plus a managed local-forward helper for external MCP clients; keep the gateway loopback-only. Serialize control operations and record configuration results separately from picture health.
- Flag sustained uniformly black Mac return frames instead of reporting picture readiness from frame flow alone.
- Use the documented hidden Broadcast launch argument.

## Unreleased — 2026-10-19

- Keep Windows OBS/Broadcast camera interfaces at 30 fps even when transport is 15 fps. A successful 15 fps capture open and flowing frames were insufficient: the observed Broadcast return was uniformly black. Mark 15 fps experimental; restoring both configurations to 30 fps recovered real video.

- Support matching optional 15 fps settings on both machines, with 30 fps camera-capture fallback and paced downstream encoding. Display the selected rate in the Mac menu.
- Record redacted native FFmpeg error details in bounded diagnostics.

- Add bounded, rotating per-second Mac diagnostics for capture, conversion, encoding, transport reads, decoding and virtual-camera submission. Record output transitions and process CPU without recording media or connection credentials.
- Restore 720p output dimensions when switching from GhaustCam to OBS, including configurations with stale 1080p overrides.
- Distinguish virtual-camera submission attempts from backend-reported drops. These counters do not certify delivery to meeting software.

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

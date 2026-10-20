# Release validation

Target: v1.0.0, 2026-09-27. Tested on an Apple Silicon M5 MacBook Air running macOS 26.3.2 and a Windows PC with an RTX 3070 Laptop GPU and NVIDIA Broadcast 2.2.1.

- Bundled macOS runtime loaded PyAV, NumPy and the OBS virtual camera backend without the development virtual environment.
- macOS application installed and launched from `/Applications`, independent of the checkout. Configuration and logs reside in the user's Application Support directory.
- Normal Windows GUI close left zero controller/worker processes and a stopped state. Reopening the service restored the Mac stream automatically. The full Windows folder was then moved outside the build checkout and successfully used from its new location.
- Mac quit released its backend; reopening restored ready state with hardware decoding.
- Windows x64 executable built on Windows with its own Python runtime, Tk UI and MediaMTX. It uses no SSH, scheduled tasks, external Python installation or OBS UI at runtime. Scheduled tasks were used only by the maintainer to launch the interactive test over SSH.
- Video-only 1280×720 at 30 fps. Windows D3D11VA decoder and NVENC encoder, Mac VideoToolbox encoder and decoder; both virtual cameras were created successfully.
- Final portable runtime passed a 120-second stability check: 60 health samples, zero samples below the 22 fps health threshold or outside the ready state, with VideoToolbox hardware decode throughout.
- Five consecutive fresh RTSP connections successfully decoded with VideoToolbox. The RTSP path preserves the previously validated 1200-byte packet limit and normal packet queue capacity. Probe decoder state is cleared before waiting for an independently decodable keyframe.
- Unit coverage includes private configuration, URL validation, credential redaction, latest-frame replacement/wakeup, decoder keyframe gating, YUV plane lifetime/padding, and an optional real VideoToolbox regression test that verifies 60 submitted frames yield 60 encoded frames with no B frames.

Hardware support on other Mac/Windows/GPU versions is not yet verified. This is an unsigned community release; it does not include platform notarization or commercial signing. First-run camera, virtual camera extension and firewall permissions still require user interaction.

Performance figures in the README are from the earlier optimized native pipeline, not a claim of a separately remeasured portable-package latency. The package preserves its 720p30 codec and frame-forwarding settings. Release smoke tests check actual frame rates and actual hardware-decoder status, rather than treating a configured frame rate as measured throughput.


## v1.1.0 automatic startup and icon

- Tested a real Windows restart with the owner's explicit consent. Windows automatically logged into the interactive desktop and started `RemoteEyeContact.exe --autostart --minimized` from its per-user startup entry. The controller then managed both video workers; no manual Windows launch was performed after restart.
- The Mac remained open during the restart and automatically reconnected. First ready state occurred within approximately 80 seconds of starting the reboot observation (includes shutdown, boot, logon and video warmup).
- This particular reboot test produced roughly 23–25 processed frames/s while the camera uplink remained about 30 fps. The output format remains 720p30; the fixed format is not a guarantee of 30 unique corrected frames/s under every Windows power/driver/background-load condition.
- A transient decoder error later activated the existing software-decoder fallback, and video recovered automatically. This test therefore verifies unattended recovery, not uninterrupted hardware decoding or a new latency benchmark.
- Windows automatic login was a separate, owner-authorized machine configuration. No login credential or automatic-login setup script is shipped. Ordinary users must choose and configure their own login policy.
- Verified the generated artwork is embedded in the Mac ICNS bundle and Windows ICO executable/window assets. Four additional tests cover startup command quoting and Broadcast launch behavior (15 total local tests, including the optional hardware encoder test).

## v1.1.1 Tailscale recovery

- Diagnosed a stopped Mac Tailscale connection: the configured Tailnet hostname did not resolve and video could not reach the otherwise running Windows service. Restoring the authenticated Tailscale connection allowed the existing pipeline to recover automatically, with approximately 25–26 processed frames/s and VideoToolbox decoding.
- Added seven network tests, covering Tailnet address classification, LAN isolation, stopped-connection recovery, login guidance without automatic authentication, bounded command timeouts, cancellation before connection, and no Tailscale polling while video is healthy. All 22 local tests passed, including the hardware encoder test.
- Verified the new helper against the installed, connected Tailscale client. The stopped-state branch is tested with mocked command results; automated tests do not disconnect the user's shared VPN.
- Rebuilt and signature-verified the Mac bundle and scanned its Python archive for deployment-specific identifiers. The rebuilt application requires renewed macOS camera consent before its end-to-end video check can complete.

## 2026-10-01 image corruption and intermittent blank output

- Compared actual frames at the Mac uplink, Windows virtual-camera input and Broadcast return. The corrupted image was already present in the uplink. Changing AVFoundation capture from NV12 to UYVY restored normal images; encoding remains hardware-accelerated NV12/H.264 at 720p30. This is an observed compatibility workaround, not a claim that every NV12 capture device is faulty.
- Reproduced repeated warmup/black output while both RTSP connections remained healthy: processed throughput briefly fell below the old continuous-readiness threshold. Readiness now latches while frames remain fresh. Genuine stale output still blanks after 0.75 seconds, with a shorter recovery warmup and no additional video queue.
- Windows waits for live input before opening Broadcast output and reopens after sustained input loss; brief input-status dips are debounced.
- All 27 local tests passed, including the hardware encoder regression test. A 90-second runtime observation produced 160 steady-state samples (after excluding the first 10 seconds), all ready, with median received throughput 29.9 fps and no additional reconnects. The user confirmed normal moving images before the final jitter fix; this measurement checks pipeline state and throughput, not an independently remeasured end-to-end latency.
- Diagnostic frames and machine-specific logs remain private and are excluded from source control and release assets.

## 2026-10-18 optional GhaustCam direct output

- Tested against the separately installed GhaustCam 1.0 extension. Renamed its device and verified discovery still works after its device UUID changes. An independent AVFoundation reader captured normal real returned video from the renamed device, without an OBS or GhaustCam GUI running.
- The extension advertises 1920x1080 BGRA. A 720p sink submission did not produce the expected image; 1080p submission did. Processing and transport remain 720p30, with local upscaling only at output.
- The first 90-second pipeline observation included startup retries and warmup. After reaching ready, all 145 sampled status records remained ready, median received throughput was 29.8 fps, and the reconnect count did not increase during that interval. This measures pipeline health, not continuous visual inspection or end-to-end latency.
- A later decoder error triggered the existing software fallback. Restarting the application restored VideoToolbox decoding and the independent reader again obtained normal video. This backend is not a guarantee of uninterrupted hardware decoding or long-session stability.
- All 30 local tests passed, including the optional hardware encoder regression. Bundle signature verification and checks for private deployment identifiers in source and the packaged Python archive passed. Diagnostic images and local connection configuration are not published.
- A second 90-second observation after restarting showed brief re-warmup events: 9 of 158 status samples after the initial 10 seconds were not ready, median received throughput was 29.75 fps, and reconnect count stayed unchanged. Occasional stalls therefore remain unresolved; this integration must not be described as a complete stability fix.

## Decoder recovery and conversion investigation

- The old Mac receiver permanently disabled hardware decoding after a single codec error and reopened RTSP. The new receiver owns a separate decoder context, discards dependent packets after an error, and creates a fresh decoder at the next keyframe without closing RTSP. Three failures without 150 successful frames activate a software cooldown. After 60 seconds, a hardware probe at a keyframe replaces software only if it produces video; failed probes leave software output running. Three consecutive software decode failures propagate to the connection loop to refresh stream parameters.
- All 36 tests passed, including the hardware encoder regression. An additional synthetic 90-frame H.264/MP4 hardware test injected an error at packet 20: 79 frames were decoded with VideoToolbox using two decoder instances, with exactly one reset; dependent frames before the next keyframe were intentionally skipped.
- A real three-minute observation before the converter change reproduced low Mac capture/send throughput and stale upstream video while Windows continued approximately 30 fps output. Hardware reset, temporary software fallback, and automatic hardware restoration were all observed. This confirms recovery behavior, but that run still contained stalls.
- Process sampling showed per-frame scaling thread creation/destruction, including thread joins during VideoFrame destruction. The Mac now reuses one VideoReformatter per worker, with one thread for uplink conversion and two for return scaling. A 120-frame local 720p NV12 to 1080p BGRA microbenchmark measured median/P95 of 7.47/17.23 ms for implicit per-frame conversion versus 3.46/4.99 ms for reused two-thread conversion. This is a conversion benchmark, not an end-to-end latency measurement.
- Pixel comparison of the previous and reused two-thread scaling paths was identical on a synthetic NV12 frame. Subsequent process sampling showed no scaling-thread creation/destruction stacks, but live upstream stalls still occurred, so this optimization alone did not fix all interruptions.
- Added a streaming-lifetime NSProcessInfo activity with user-initiated and latency-critical options, plus user-initiated video-worker QoS. Verified the live-video assertion exists and its standalone lifecycle releases cleanly. All 38 tests passed including the hardware test. This change requests scheduling appropriate for active video without changing global power preferences.
- The final three-minute Tailscale-path observation still contained 9 non-ready status samples out of 178, three decoder events and three freshness losses, despite a 29.8 fps median. Scheduling improvements are therefore not a complete fix. A concurrent independent LAN decoder received 5,117 frames entirely with VideoToolbox and no decoder resets; its final network interruption coincided with the intentional application restart. These differing consumers are not a controlled end-to-end network benchmark. Further LAN application validation follows locally.
- LAN application testing also encountered VideoToolbox decoder resets, so the network-path change did not eliminate the decoder defect. The default Mac return decoder is now software; hardware decoding remains an explicit opt-in. A synthetic 720p 90-frame clip decoded five times measured median per-frame time of 0.723 ms in software versus 1.075 ms with VideoToolbox. This small uniform-image clip is not representative of every video workload and does not establish a full latency or power comparison. Hardware encoding and Windows acceleration remain enabled.
- After renewed camera consent, the final software-decoding build was observed over LAN for 179.8 seconds: all 180 status samples were ready, median received throughput was 29.8 fps, and decoder-event, freshness-loss and reconnect counters did not increase. An independent AVFoundation reader obtained a normal image from the renamed virtual camera. This is a three-minute pipeline-health test, not continuous visual inspection, a Teams endurance test, or proof that all long-session failures are eliminated. All 39 automated tests had passed, including the optional hardware encoder regression.

## Two-hour endurance test — 2026-10-18

- Completed a 7,200-second observation of the software-decoding LAN configuration with 7,200 one-second status samples. No missing/stale status records, process restarts, additional RTSP reconnects or decoder events were recorded. Median received throughput was 29.7 fps.
- **Failed the uninterrupted-video criterion.** There were 60 non-ready samples across 11 episodes (longest: 15 consecutive samples), and 28 additional freshness-loss events. The ready-sample fraction was 99.17%; this is not a measurement of the exact percentage of normal output frames.
- The independent virtual-camera reader obtained images in all 25 checks, but one image was completely black. Checks ran approximately every five minutes, so they cannot exclude additional short blackouts or frozen frames. Images were reduced to local statistics and deleted, not recorded continuously or published.
- Windows status was read successfully 236 times, approximately every 30 seconds. This interval cannot attribute second-scale interruptions to a particular Windows stage. Several Mac interruptions coincided with reduced capture/send/receive throughput; the available evidence does not establish a single network or hardware root cause.
- Backend RSS was 169.8 MiB initially, 142.1 MiB at the end, and at most 186.3 MiB in sampled measurements. No sustained memory growth was observed. Sampled `ps` CPU values had a median of 58.3% and a maximum of 111.0% (100% represents approximately one logical CPU); these are process-average estimates, not instantaneous peak utilization.
- The two-hour findings supersede any inference of long-session stability from the earlier three-minute pass. Further work should correlate per-stage frame timing with continuous output-frame diagnostics before claiming that blackouts are fixed.


## 2026-10-19 OBS 720p diagnostics (not a stability certification)

- Switched the test installation from GhaustCam 1080p BGRA to OBS 720p I420 without opening OBS. Added rotating per-stage timing and output-transition logs.
- A 319-second observation contained 307 health samples, 279 ready samples, median received throughput 29.8 fps and median process CPU 41.9% (100% represents one core). Ten additional freshness-loss events occurred after the first sample. Build and diagnostic activity shared the machine during part of this interval; this is not a controlled performance comparison.
- Stable return conversion took approximately 0.2–0.4 ms in sampled intervals. Stalls affected several local stages simultaneously; the logs do not establish a single root cause or prove the network is responsible.
- A separate 60-second live VideoToolbox decoding probe decoded 1,738 frames without decoder errors, with one gap of 347 ms. This short test does not supersede earlier long-session hardware failures. Software remains the default Mac decoder; hardware encoding and Windows acceleration remain enabled.
- All 44 tests passed, including the optional real hardware encoder regression. Packaged Python archive privacy scan and bundle signature verification passed. Meeting-client delivery and uninterrupted long-session operation remain unverified for this build.


## 2026-10-19 optional 15 fps and Mac hardware decoding

- Both local configurations selected 15 fps; Mac selected VideoToolbox decoding with existing recovery and software fallback. The Mac camera rejected native 720p15, so capture fell back to 30 fps with newest-frame selection before 15 fps uplink encoding.
- A 120-second observation collected 120 health samples, including 109 ready samples after startup. Ready samples used VideoToolbox throughout, with median return throughput 14.9 fps and median Mac process CPU 22.5% (one core = 100%). No new freshness losses or decoder reset events occurred after the first ready sample. This is a short pipeline-health test, not continuous meeting-client visual validation or long-session certification.
- Earlier 30 fps software observations had a 41.9% CPU median, but workload and timing were not controlled; this is not a rigorous efficiency benchmark. Camera capture and Broadcast inference work are not guaranteed to halve.
- Windows readiness thresholds now scale with the selected rate instead of rejecting healthy 15 fps streams. All 45 tests passed, including the real hardware encoder regression.


## Follow-up: 15 fps visual validation failed

The preceding 15 fps health test did NOT establish usable video: subsequent investigation found normal raw uplink content but uniformly black processed frames with both software and hardware Mac decoders. Returning Windows camera interfaces to 30 fps initially produced a Broadcast placeholder; restoring both configurations to 30 fps and restarting Broadcast restored a real scene, independently decoded and visually inspected on Mac. VideoToolbox remained enabled. The 15 fps profile is experimental and must not be presented as validated or stable. Frame flow alone is insufficient acceptance evidence. No meeting-client visual confirmation is implied by the RTSP image check.


## 2026-10-20 Broadcast 2.3 integration

- Inspected installed Broadcast 2.3.0.13104 and successfully initialized its loopback MCP gateway, verifying server identity `nvidia-broadcast` version 2.3.0. Live device discovery advertised OBS input only at 1280x720/30 fps.
- Tested remote `status` and idempotent `prepare` from Mac through authenticated SSH using the newly packaged Windows executable. Repeated preparation returned no changes; the controller's background configuration check also succeeded. Only Eye Contact was enabled among camera effects.
- Independently tested HTTP MCP through an SSH local forward, including the tunnel helper's start/stop/restart cycle and remote preparation without changes. No LAN MCP listener or firewall port was added.
- Updated both installed applications, verified the Mac signature and scanned the Python archive/source for private deployment identifiers. All 59 Mac tests passed, including hardware encoding; all 14 new control/picture tests passed on Windows. File-processing restore behavior and partial failures have unit coverage; no real user file-processing job was interrupted to test them.
- A real processed RTSP frame was independently decoded and visually inspected as a camera scene rather than a blank or NVIDIA placeholder. This does not certify continuous meeting-client output or gaze-correction accuracy.
- A subsequent 120-sample observation spanning 119.7 seconds was ready throughout, with median return throughput 29.8 fps and median process CPU 34.5% of one core. There were zero additional freshness losses, zero uniform-black flags, and zero decoder events. This short test is not long-session stability certification or an end-to-end latency benchmark.

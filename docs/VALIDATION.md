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

# Dependency sources and redistribution

The project's original source code is MIT licensed. This does not replace any third-party license. The prebuilt applications contain copyleft components, including pyvirtualcam, FFmpeg and codec libraries; their applicable redistribution terms still apply to the combined binary distribution. A permissive license for this repository is not permission to redistribute the bundled dependencies under MIT alone.

Every binary release must include a matching `Remote-Eye-Contact-dependency-sources.tar.gz` beside the application downloads, and the application's own source must be available at the corresponding Git tag. The dependency source archive contains the upstream source archives, SHA-256 manifest, and build recipes/patches used by the PyAV wheel's FFmpeg vendor build. `source-manifest.json` records exact upstream versions and checksums. License notices accompany the executables.

Versions in the initial release:

- macOS: Python 3.12.14, PyAV 18.1.0, NumPy 2.5.3, pyvirtualcam 0.15.0.
- Windows: Python 3.12.10, PyAV 18.0.0, NumPy 2.4.3, pyvirtualcam 0.15.0, MediaMTX 1.21.1.
- PyInstaller 6.22.0 with its bootloader distribution exception.
- Both PyAV wheels use the `8.1.2-1` vendor build of FFmpeg 8.1.2 from [PyAV-Org/pyav-ffmpeg](https://github.com/PyAV-Org/pyav-ffmpeg/tree/8.1.2-1).

To rebuild third-party components, unpack the corresponding source archive and follow its upstream README/build scripts. For FFmpeg use the included pyav-ffmpeg repository's `scripts/build-ffmpeg.py`, `scripts/pkg.py`, `.github/workflows/build-ffmpeg.yml`, and `patches/`; these specify toolchains, platform options, exact source revisions and modifications. Do not substitute a stock FFmpeg configuration and call it the matching vendor build.

To build pyvirtualcam, unpack its source, then unpack the `libyuv` source into `external/libyuv`. The revision matches the upstream v0.15.0 submodule. Follow its platform-specific `.github/scripts/build-*` scripts. Build PyAV against the reconstructed FFmpeg libraries, then use the main repository's platform build scripts to assemble the application. The bundles contain replaceable shared libraries; they are not statically combined with the application executable. On macOS, re-sign a locally modified bundle ad hoc after replacing libraries.

Source archives preserve upstream licenses. NVIDIA Broadcast, the NVIDIA driver, and OBS installers are not redistributed. Source archive preparation is described by `scripts/fetch-dependency-sources.py`; it verifies pinned hashes before writing release assets.

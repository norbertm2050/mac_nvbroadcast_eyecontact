# Third-party software

The original application source is MIT licensed. Binary bundles must also comply with the licenses of their included components; MIT does not override those terms.

Remote Eye Contact uses PyAV (BSD-3-Clause), NumPy (BSD-3-Clause with bundled-library notices), pyvirtualcam (GPL-2.0), Python (PSF license), and PyInstaller (GPL with a bootloader distribution exception). Windows packages also include MediaMTX 1.21.1 (MIT). Their license texts and bundled dependency notices are included in `licenses/`.

PyAV binary wheels contain FFmpeg and additional codec libraries. Distribution must include the matching corresponding source and build instructions for the copyleft components, alongside the application source. See `docs/DEPENDENCIES.md` and the release source archive.

NVIDIA Broadcast, NVIDIA GPU drivers, and OBS Studio/its virtual camera installation are **not bundled**. Install these separately from their official distributors. These products and their trademarks belong to their respective owners. This project is not affiliated with NVIDIA, OBS, Apple, or Tailscale.

"""Download the pinned upstream Windows binary and verify its published checksum."""

import hashlib
from pathlib import Path
import urllib.request
import zipfile
import io

version = "v1.21.1"
asset = "mediamtx_" + version + "_windows_amd64.zip"
base = f"https://github.com/bluenviron/mediamtx/releases/download/{version}/"
checksums = (
    urllib.request.urlopen(base + "checksums.sha256", timeout=60).read().decode()
)
expected = next(
    line.split()[0]
    for line in checksums.splitlines()
    if line.split()[-1].lstrip("*") == asset
)
body = urllib.request.urlopen(base + asset, timeout=120).read()
assert hashlib.sha256(body).hexdigest() == expected, "MediaMTX checksum mismatch"
root = Path(__file__).resolve().parents[1]
(root / "vendor").mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(body)) as z:
    (root / "vendor/mediamtx.exe").write_bytes(z.read("mediamtx.exe"))
    (root / "licenses/MediaMTX-LICENSE").write_bytes(z.read("LICENSE"))
print("Verified", asset, expected)

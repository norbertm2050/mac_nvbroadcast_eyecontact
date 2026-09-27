"""Fetch and verify the exact matching third-party source release asset."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
manifest = Path(__file__).with_name("source-manifest.json")
items = json.loads(manifest.read_text())
dest = root / "dist/dependency-sources"
dest.mkdir(parents=True, exist_ok=True)


def fetch(item):
    path = dest / item["file"]
    if not path.exists():
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--max-time",
                "180",
                "--retry",
                "2",
                item["url"],
                "--output",
                str(path),
            ],
            check=True,
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError("Checksum mismatch: " + item["name"])
    return item["name"]


with ThreadPoolExecutor(max_workers=4) as pool:
    for name in pool.map(fetch, items):
        print("Verified", name)
(dest / "source-manifest.json").write_bytes(manifest.read_bytes())
(dest / "BUILD-INSTRUCTIONS.md").write_bytes(
    (root / "docs/DEPENDENCIES.md").read_bytes()
)
with tarfile.open(
    root / "dist/Remote-Eye-Contact-dependency-sources.tar.gz", "w:gz"
) as archive:
    for path in sorted(dest.iterdir()):
        archive.add(path, arcname="dependency-sources/" + path.name, recursive=False)

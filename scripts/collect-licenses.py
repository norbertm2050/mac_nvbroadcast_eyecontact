"""Collect all notices provided by the exact installed wheel distributions."""

import importlib.metadata as metadata
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] / "licenses"
for name in [
    "av",
    "pyvirtualcam",
    "numpy",
    "pyinstaller",
    "setuptools",
    "packaging",
    "altgraph",
]:
    dist = metadata.distribution(name)
    for file in dist.files or []:
        if ".dist-info/licenses/" in str(file):
            out = root / name / str(file).split("/licenses/", 1)[1]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(dist.locate_file(file).read_bytes())
# Python builds distribute their notices under the installation prefix.
for filename in ["LICENSE.txt", "LICENSE"]:
    source = Path(sys.base_prefix) / filename
    if source.exists():
        (root / "Python-LICENSE.txt").write_bytes(source.read_bytes())
        break
print("Collected dependency notices in", root.name)

"""Build the Strands Lambda layer for linux/arm64 without Docker.

    python scripts/build_layer.py

Installs layers/strands/requirements.txt as prebuilt manylinux aarch64 wheels into
layers/strands/python/, the folder Lambda puts on the path as /opt/python. Run it before
`sam build`; the template packages the folder as it is.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYER = ROOT / "layers" / "strands"
TARGET = LAYER / "python"


def main() -> int:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    uv = shutil.which("uv")
    if not uv:
        print("uv is not on PATH: https://docs.astral.sh/uv/", file=sys.stderr)
        return 1
    cmd = [
        uv, "pip", "install",
        "--target", str(TARGET),
        "--python-platform", "aarch64-manylinux2014",
        "--python-version", "3.12",
        "--no-build",
        "-r", str(LAYER / "requirements.txt"),
    ]
    result = subprocess.run(cmd, check=False)  # noqa: S603  (fixed args)
    if result.returncode != 0:
        return result.returncode
    # boto3 and botocore are already in the Lambda runtime; leaving them out keeps the layer small.
    for name in ("boto3", "botocore", "s3transfer"):
        for path in TARGET.glob(f"{name}*"):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    size = sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file()) / 1e6
    print(f"layer ready: {TARGET} ({size:.1f} MB unzipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

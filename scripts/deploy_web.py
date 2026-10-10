"""Build the web app against an API and publish it to Amplify Hosting (manual deploy, no Git link).

    python scripts/deploy_web.py --app-id dzxkrtlc7xqfx --api-url https://xxxx.execute-api.ap-south-1.amazonaws.com

Uses the AWS CLI for the Amplify calls (so `aws login` and CI role credentials both work) and
uploads the zip to the presigned URL Amplify returns. Pass --profile locally; CI uses the
environment's credentials.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DONE = ("SUCCEED", "FAILED", "CANCELLED")


def tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        sys.exit(f"{name} is not on PATH")
    return found


def aws(profile: str | None, *args: str) -> dict[str, Any]:
    cmd = [tool("aws"), *args, "--output", "json"]
    if profile:
        cmd += ["--profile", profile]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603  (fixed args)
    return json.loads(out.stdout or "{}")


def build(api_url: str) -> None:
    env = {**os.environ, "VITE_API_URL": api_url, "VITE_USE_MOCKS": "false"}
    subprocess.run([tool("npm"), "run", "build"], cwd=WEB, env=env, check=True)  # noqa: S603


def zipped(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())
    return buf.getvalue()


def upload(url: str, data: bytes) -> int:
    if not url.startswith("https://"):
        sys.exit("Amplify returned an upload URL that is not https")
    req = urllib.request.Request(  # noqa: S310  (https checked above)
        url, data=data, method="PUT", headers={"Content-Type": "application/zip"}
    )
    with urllib.request.urlopen(req) as reply:  # noqa: S310
        return int(reply.status)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--app-id", required=True)
    p.add_argument("--api-url", required=True)
    p.add_argument("--branch", default="main")
    p.add_argument("--profile", default=None, help="AWS profile, e.g. thirst (omit in CI)")
    p.add_argument("--skip-build", action="store_true")
    a = p.parse_args()
    where = ["--app-id", a.app_id, "--branch-name", a.branch]

    if not a.skip_build:
        build(a.api_url)
    data = zipped(WEB / "dist")
    dep = aws(a.profile, "amplify", "create-deployment", *where)
    print(f"uploaded {len(data) // 1024} KB ({upload(dep['zipUploadUrl'], data)})")
    job = dep["jobId"]
    aws(a.profile, "amplify", "start-deployment", *where, "--job-id", job)
    status = "PENDING"
    for _ in range(100):
        reply = aws(a.profile, "amplify", "get-job", *where, "--job-id", job)
        status = reply["job"]["summary"]["status"]
        if status in DONE:
            break
        time.sleep(3)
    print(f"job {job}: {status}")
    return 0 if status == "SUCCEED" else 1


if __name__ == "__main__":
    sys.exit(main())

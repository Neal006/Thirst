"""Write tests/vectors/hmac.json, the shared HMAC test vectors (plan 08 §6).

The CLI tests and the API tests both read this file, so the client and the server can never
drift apart. The secret here is a test value only; the real secret lives in SSM.

    python scripts/gen_hmac_vectors.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "tests" / "vectors" / "hmac.json"
SERVER_SECRET = "test-secret-not-for-prod"  # noqa: S105  (a published test value, not a secret)
SITE_ID = "s_abcdefghij"
TS = 1760030000
BODY = '{"job_id":"j_aaaaaaaaaaaa","site_id":"s_abcdefghij"}'


def _hex(key: bytes, message: bytes) -> str:
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def build() -> dict[str, Any]:
    token = _hex(SERVER_SECRET.encode(), SITE_ID.encode())

    def signature(body: str) -> str:
        return _hex(token.encode("ascii"), str(TS).encode("ascii") + b"." + body.encode())

    return {
        "server_secret": SERVER_SECRET,
        "site_id": SITE_ID,
        "token": token,
        "ts": TS,
        "body": BODY,
        "signature": signature(BODY),
        "signature_trailing_space": signature(BODY + " "),
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

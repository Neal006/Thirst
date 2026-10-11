"""The id shapes shared by the CLI and the server (contract 08 §2), defined once."""

from __future__ import annotations

import re

SITE_ID = re.compile(r"s_[a-z2-7]{10}")
PLAN_ID = re.compile(r"p_[a-z2-7]{10}")
JOB_ID = re.compile(r"j_[a-z2-7]{12}")
TOKEN = re.compile(r"[0-9a-f]{64}")
RECEIPT_PATH = re.compile(r"/receipts/s_[a-z2-7]{10}/j_[a-z2-7]{12}")

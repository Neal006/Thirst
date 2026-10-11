"""Read and write ``~/.thirst/config.toml`` (plan 04.1, contract 08 §2.6).

The file holds ``api_url``, ``site_id`` and ``token``. ``THIRST_API_URL`` and ``THIRST_TOKEN``
override the file. The token is a secret: it is never printed, logged or put in an error message.
"""

from __future__ import annotations

import contextlib
import os
import re
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomli_w

from .errors import ConfigError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib

HOME_ENV = "THIRST_HOME"
URL_ENV = "THIRST_API_URL"
CREDENTIAL_ENV = "THIRST_TOKEN"

# The hosted service, used when neither --api-url nor THIRST_API_URL is given.
DEFAULT_API_URL = "https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com"
DEFAULT_WEB_URL = "https://main.dzxkrtlc7xqfx.amplifyapp.com"

_SITE_ID = re.compile(r"s_[a-z2-7]{10}")
_TOKEN = re.compile(r"[0-9a-f]{64}")
_REGISTER_FIRST = "Run `thirst register` first."


@dataclass(frozen=True)
class Config:
    api_url: str
    site_id: str
    token: str = field(repr=False)


def thirst_home(env: Mapping[str, str] | None = None) -> Path:
    """The state directory: ``$THIRST_HOME`` if set, else ``~/.thirst``."""
    source = os.environ if env is None else env
    override = source.get(HOME_ENV)
    if override:
        return Path(override)
    return Path(os.path.expanduser("~")) / ".thirst"


def config_path() -> Path:
    return thirst_home() / "config.toml"


def outbox_dir() -> Path:
    return thirst_home() / "outbox"


def receipts_dir() -> Path:
    return thirst_home() / "receipts"


def logs_dir() -> Path:
    return thirst_home() / "logs"


def restore_marker_path() -> Path:
    return thirst_home() / "restore.json"


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_URL_HELP = (
    "api_url must start with https:// (http:// is only allowed for localhost), "
    "and must not contain a user name or password."
)


def check_api_url(raw: str) -> str:
    """The URL without a trailing slash, or ``ConfigError``.

    The site token travels in requests to this address, so it must be ``https://``. Plain
    ``http://`` is accepted only for loopback hosts (local development). A URL with a user name or
    password in it is refused.
    """
    url = raw.strip().rstrip("/")
    if re.search(r"\s", url):
        raise ConfigError(_URL_HELP)
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError for a bad port
    except ValueError:
        raise ConfigError(_URL_HELP) from None
    if not host or "@" in parts.netloc:
        raise ConfigError(_URL_HELP)
    if parts.scheme == "https" or (parts.scheme == "http" and host in _LOOPBACK_HOSTS):
        return url
    raise ConfigError(_URL_HELP)


def validated(cfg: Config) -> Config:
    """Return the config with a normalised URL, or raise ``ConfigError`` naming the bad key."""
    url = check_api_url(cfg.api_url)
    if not _SITE_ID.fullmatch(cfg.site_id):
        raise ConfigError("site_id in config.toml is not a valid site id, such as s_abcdefghij.")
    if not _TOKEN.fullmatch(cfg.token):
        raise ConfigError("token must be 64 lowercase hex characters. Run `thirst register` again.")
    return replace(cfg, api_url=url)


def _read_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(f"Could not read {path}: {exc.strerror or 'unknown error'}.") from None
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        raise ConfigError(
            f"{path} is not valid TOML. Fix it, or delete it and run `thirst register`."
        ) from None


def _text(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{key} is missing from config.toml. Run `thirst register` first.")
    return value


def load(env: Mapping[str, str] | None = None) -> Config:
    """Read the config, apply the env overrides and validate it."""
    source = os.environ if env is None else env
    data = _read_file(config_path())
    url = source.get(URL_ENV) or data.get("api_url")
    token = source.get(CREDENTIAL_ENV) or data.get("token")
    site = data.get("site_id")
    if not data and not (url and token and site):
        raise ConfigError(_REGISTER_FIRST)
    return validated(
        Config(
            api_url=_text(url, "api_url"),
            site_id=_text(site, "site_id"),
            token=_text(token, "token"),
        )
    )


def write_private(path: Path, text: str) -> None:
    """Write ``text`` atomically: a temp file (mode 0600), then ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        if os.name != "nt":
            os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


def save(cfg: Config) -> Path:
    """Validate and write the config. Returns the path."""
    good = validated(cfg)
    body = {"api_url": good.api_url, "site_id": good.site_id, "token": good.token}
    path = config_path()
    write_private(path, tomli_w.dumps(body))
    return path

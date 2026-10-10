"""Plan 04.1: config file handling (path, keys, env overrides, modes, bad files)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from thirst import config
from thirst.errors import ConfigError

TOKEN = "93ec2d429dfd3e011895ec55f2c376fed4534e588f27488ecc3bf1074433d80f"
SITE = "s_abcdefghij"
URL = "https://abc.execute-api.ap-south-1.amazonaws.com"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / ".thirst"
    monkeypatch.setenv("THIRST_HOME", str(target))
    for name in ("THIRST_API_URL", "THIRST_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    return target


def make_config() -> config.Config:
    return config.Config(api_url=URL, site_id=SITE, token=TOKEN)


def test_save_then_load_round_trips(home: Path) -> None:
    config.save(make_config())

    assert (home / "config.toml").is_file()
    assert config.load() == make_config()


def test_default_home_is_dot_thirst_in_the_user_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("THIRST_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert config.thirst_home() == tmp_path / ".thirst"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_config_file_mode_is_0600(home: Path) -> None:
    config.save(make_config())

    mode = stat.S_IMODE((home / "config.toml").stat().st_mode)
    assert mode == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_overwriting_keeps_mode_0600(home: Path) -> None:
    config.save(make_config())
    config.save(make_config())

    assert stat.S_IMODE((home / "config.toml").stat().st_mode) == 0o600


def test_save_leaves_no_temp_files(home: Path) -> None:
    config.save(make_config())

    assert sorted(p.name for p in home.iterdir()) == ["config.toml"]


def test_env_overrides_file(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config.save(make_config())
    monkeypatch.setenv("THIRST_API_URL", "https://other.example.com")
    monkeypatch.setenv("THIRST_TOKEN", "ab" * 32)

    loaded = config.load()

    assert loaded.api_url == "https://other.example.com"
    assert loaded.token == "ab" * 32
    assert loaded.site_id == SITE


def test_missing_config_asks_to_register(home: Path) -> None:
    with pytest.raises(ConfigError) as err:
        config.load()

    assert "Run `thirst register` first" in err.value.message
    assert err.value.exit_code == 3


def test_corrupt_toml_gives_a_plain_error(home: Path) -> None:
    home.mkdir(parents=True)
    (home / "config.toml").write_text(f'token = "{TOKEN}\nthis is = = not toml', encoding="utf-8")

    with pytest.raises(ConfigError) as err:
        config.load()

    assert "config.toml" in err.value.message
    assert TOKEN not in err.value.message


@pytest.mark.parametrize("missing", ["api_url", "site_id", "token"])
def test_missing_key_is_named(home: Path, missing: str) -> None:
    values = {"api_url": URL, "site_id": SITE, "token": TOKEN}
    del values[missing]
    home.mkdir(parents=True)
    body = "".join(f'{k} = "{v}"\n' for k, v in values.items())
    (home / "config.toml").write_text(body, encoding="utf-8")

    with pytest.raises(ConfigError) as err:
        config.load()

    assert missing in err.value.message


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("token", "not-hex"),
        ("token", "AB" * 32),
        ("site_id", "s_ABCDEFGHIJ"),
        ("site_id", "abc"),
        ("api_url", "ftp://example.com"),
        ("api_url", "example.com"),
    ],
)
def test_invalid_values_are_rejected_without_echoing_the_token(
    home: Path, field: str, bad: str
) -> None:
    values = {"api_url": URL, "site_id": SITE, "token": TOKEN, field: bad}
    home.mkdir(parents=True)
    body = "".join(f'{k} = "{v}"\n' for k, v in values.items())
    (home / "config.toml").write_text(body, encoding="utf-8")

    with pytest.raises(ConfigError) as err:
        config.load()

    assert field in err.value.message
    assert TOKEN not in err.value.message


def test_save_rejects_an_invalid_config(home: Path) -> None:
    bad = config.Config(api_url=URL, site_id=SITE, token="short")

    with pytest.raises(ConfigError):
        config.save(bad)
    assert not (home / "config.toml").exists()


def test_repr_never_shows_the_token() -> None:
    assert TOKEN not in repr(make_config())
    assert TOKEN not in str(make_config())


def test_api_url_trailing_slash_is_dropped(home: Path) -> None:
    config.save(config.Config(api_url=URL + "/", site_id=SITE, token=TOKEN))

    assert config.load().api_url == URL


def test_paths_live_under_the_home(home: Path) -> None:
    assert config.outbox_dir() == home / "outbox"
    assert config.receipts_dir() == home / "receipts"
    assert config.logs_dir() == home / "logs"
    assert config.restore_marker_path() == home / "restore.json"

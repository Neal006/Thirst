"""Shared fixtures for the handler tests: moto DynamoDB and SSM with the real table layout."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from handlers import security, store

REGION = "ap-south-1"
STAGE = "test"


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A mocked AWS account with the four tables created from ``store.TABLE_SPECS``."""
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",  # noqa: S106
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": REGION,
        "SERVER_SECRET_PARAM": "/thirst/server_secret",
    }.items():
        monkeypatch.setenv(key, value)
    for name, spec in store.TABLE_SPECS.items():
        monkeypatch.setenv(spec.env, f"thirst-{STAGE}-{name}")
    security.load_secret.cache_clear()
    store.get_tables.cache_clear()
    with mock_aws():
        client = boto3.client("dynamodb", region_name=REGION)
        for name, spec in store.TABLE_SPECS.items():
            client.create_table(
                TableName=f"thirst-{STAGE}-{name}",
                BillingMode="PAY_PER_REQUEST",
                **spec.create_args(),
            )
        yield
    security.load_secret.cache_clear()
    store.get_tables.cache_clear()


@pytest.fixture
def tables(aws: None) -> store.Tables:
    return store.get_tables()

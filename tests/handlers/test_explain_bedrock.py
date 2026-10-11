import os

import pytest
from api_helpers import Client

from handlers import explain


@pytest.fixture
def ex(client: Client, monkeypatch: pytest.MonkeyPatch) -> Client:
    """Same mocked account with explain handler"""
    monkeypatch.setattr(explain, "_now", client.clock)
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    return Client(explain.handler, client.clock, client.tables)


def test_empty_model_id_uses_template(ex: Client) -> None:
    os.environ.pop('BEDROCK_MODEL_ID', None)
    response = ex.call('POST', '/explain', {'text': 'test'}).json
    assert response['source'] == 'template'
    assert response['note'] == 'agent_disabled'


def test_authorization_error_returns_bedrock_not_authorized(monkeypatch, ex: Client) -> None:
    os.environ['BEDROCK_MODEL_ID'] = 'test-model'
    def broken_runner(ctx):
        err = Exception('Access denied')
        err.response = {'Error': {'Code': 'AccessDeniedException'}}
        raise err
    monkeypatch.setattr(explain, '_build_runner', lambda: broken_runner)
    response = ex.call('POST', '/explain', {'text': 'test'}).json
    assert response['source'] == 'template'
    assert response['note'] == 'bedrock_not_authorized'
    del os.environ['BEDROCK_MODEL_ID']


def test_validation_exception_returns_bedrock_not_authorized(monkeypatch, ex: Client) -> None:
    os.environ['BEDROCK_MODEL_ID'] = 'test-model'
    def broken_runner(ctx):
        err = Exception('Invalid operation')
        err.response = {'Error': {'Code': 'ValidationException'}}
        raise err
    monkeypatch.setattr(explain, '_build_runner', lambda: broken_runner)
    response = ex.call('POST', '/explain', {'text': 'test'}).json
    assert response['source'] == 'template'
    assert response['note'] == 'bedrock_not_authorized'
    del os.environ['BEDROCK_MODEL_ID']

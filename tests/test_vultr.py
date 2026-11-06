import json
from urllib.error import HTTPError

import pytest

import inference
from policies import evaluate_policy


class Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_vultr_calls_real_endpoint_with_structured_feedback(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'vultr')
    monkeypatch.setenv('VULTR_INFERENCE_BASE_URL', 'https://api.vultrinference.com/v1')
    monkeypatch.setenv('VULTR_INFERENCE_API_KEY', 'test-secret')
    monkeypatch.setenv('VULTR_MODEL', 'test-model')
    calls = []
    responses = iter([
        'Customer-level records and revenue data.',
        'Provide revenue aggregated by customer segment for this report.',
        'I can provide the aggregate artifact for this report.',
    ])

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response(next(responses))

    monkeypatch.setattr(inference, 'urlopen', fake_urlopen)
    monkeypatch.setattr(inference.json, 'load', lambda response: {'choices': [{'message': {'content': response.content}}]})
    provider = inference.get_provider()
    original = provider.get_initial_request()
    feedback = evaluate_policy(original)
    replanned = provider.get_replanned_request(feedback)
    scoped = provider.get_scoped_response(replanned)
    assert feedback['status'] == 'denied'
    assert evaluate_policy(replanned)['status'] == 'approved'
    assert 'aggregate' in scoped
    assert len(calls) == 3
    for request, timeout in calls:
        assert request.full_url == 'https://api.vultrinference.com/v1/chat/completions'
        assert request.get_header('Authorization') == 'Bearer test-secret'
        assert timeout == 60
        body = json.loads(request.data)
        assert body['model'] == 'test-model'
    assert 'customer_level_records_restricted' in json.loads(calls[1][0].data)['messages'][1]['content']


def test_vultr_never_falls_back_without_credentials(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'vultr')
    monkeypatch.delenv('VULTR_INFERENCE_API_KEY', raising=False)
    monkeypatch.setenv('VULTR_INFERENCE_BASE_URL', 'https://api.vultrinference.com/v1')
    monkeypatch.setenv('VULTR_MODEL', 'test-model')
    with pytest.raises(RuntimeError, match='requires'):
        inference.get_provider()


def test_vultr_http_failure_does_not_expose_key(monkeypatch):
    monkeypatch.setenv('VULTR_INFERENCE_BASE_URL', 'https://api.vultrinference.com/v1')
    monkeypatch.setenv('VULTR_INFERENCE_API_KEY', 'test-secret')
    monkeypatch.setenv('VULTR_MODEL', 'test-model')
    def fail(request, timeout):
        raise HTTPError(request.full_url, 401, 'test-secret', {}, None)
    monkeypatch.setattr(inference, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='HTTP 401') as exc:
        inference.VultrProvider().get_initial_request()
    assert 'test-secret' not in str(exc.value)


def test_provider_failure_is_reported_without_mock_fallback(monkeypatch):
    from app import run_demo
    monkeypatch.setenv('VULTR_INFERENCE_BASE_URL', 'https://api.vultrinference.com/v1')
    monkeypatch.setenv('VULTR_INFERENCE_API_KEY', 'test-secret')
    monkeypatch.setenv('VULTR_MODEL', 'test-model')
    def fail(request, timeout):
        raise HTTPError(request.full_url, 401, 'unauthorized', {}, None)
    monkeypatch.setattr(inference, 'urlopen', fail)
    result = run_demo(inference.VultrProvider())
    assert result['status'] == 'failed'
    assert result['failure'] == 'Vultr inference HTTP 401'
    assert result['inference']['provider'] == 'vultr'
    assert result['inference']['completed_steps'] == []
    assert result['execution']['agent_a'] is None
    assert result['audit']['timeline'] == ['FAILED']


def test_denied_replan_gets_structured_feedback_and_retries():
    from app import run_demo
    from inference import MockProvider

    class RetryProvider(MockProvider):
        def __init__(self):
            self.feedback = []

        def get_replanned_request(self, feedback):
            self.feedback.append(feedback)
            if len(self.feedback) == 1:
                return 'Provide revenue by segment, excluding customer-level records.'
            return 'Provide aggregated revenue by segment for this report.'

    provider = RetryProvider()
    result = run_demo(provider)
    assert result['status'] == 'complete'
    assert len(provider.feedback) == 2
    assert provider.feedback[0]['reason'] == 'customer_level_records_restricted'
    assert provider.feedback[1]['status'] == 'denied'
    assert len(next(entry for entry in result['audit']['entries'] if entry['label'] == 'REPLAN')['payload']['attempts']) == 2
    assert result['audit']['timeline'] == ['REQUEST', 'DENIED', 'REPLAN', 'AGREEMENT', 'EXECUTE', 'VERIFY', 'COMPLETE']

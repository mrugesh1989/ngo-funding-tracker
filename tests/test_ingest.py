"""Ingestion adapter tests with a mocked HTTP transport."""

import httpx
import pytest

from ngo_tracker import ingest
from ngo_tracker.errors import ExternalServiceError
from ngo_tracker.ingest import fetch_nonprofits, ingest_nonprofits
from ngo_tracker.repository import search_entities


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Disable backoff sleeps so retry tests run instantly."""
    monkeypatch.setattr(ingest, "_backoff", lambda attempt: None)


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_success():
    def handler(request):
        assert request.url.params["q"] == "health"
        return httpx.Response(200, json={"organizations": [{"name": "GLOBAL HEALTH ORG", "ein": 123}]})

    orgs = fetch_nonprofits("health", client=_client(handler))
    assert orgs[0]["name"] == "GLOBAL HEALTH ORG"


def test_fetch_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"organizations": []})

    assert fetch_nonprofits("x", client=_client(handler)) == []
    assert calls["n"] == 3


def test_fetch_retry_exhaustion_raises_retryable():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(ExternalServiceError) as excinfo:
        fetch_nonprofits("x", client=_client(handler))
    assert excinfo.value.retryable is True


def test_fetch_non_retryable_status_raises_immediately():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400)

    with pytest.raises(ExternalServiceError):
        fetch_nonprofits("x", client=_client(handler))
    assert calls["n"] == 1


def test_fetch_transport_error_raises_retryable():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(ExternalServiceError) as excinfo:
        fetch_nonprofits("x", client=_client(handler))
    assert excinfo.value.retryable is True


def test_ingest_upserts_entities(session):
    def handler(request):
        return httpx.Response(
            200,
            json={"organizations": [
                {"name": "CLEAN WATER FUND", "ein": 987654321},
                {"name": None, "ein": 1},
            ]},
        )

    count = ingest_nonprofits(session, "water", client=_client(handler))
    assert count == 1
    results, _ = search_entities(session, "Clean Water")
    assert results[0].type == "ngo"

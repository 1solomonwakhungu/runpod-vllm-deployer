from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from runpod_vllm.client import RunPodClient, parse_retry_after
from runpod_vllm.errors import ApiError, ExitCode, NetworkError, RateLimitError


def _sequence(
    responses: list[httpx.Response],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[str]]:
    calls: list[str] = []
    remaining: Iterator[httpx.Response] = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return next(remaining)

    return handler, calls


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    sleeps: list[float],
    *,
    random_value: float = 1.0,
    max_retries: int = 5,
    backoff_base: float = 1.0,
    backoff_cap: float = 60.0,
) -> RunPodClient:
    return RunPodClient(
        "key",
        transport=httpx.MockTransport(handler),
        max_retries=max_retries,
        backoff_base=backoff_base,
        backoff_cap=backoff_cap,
        sleep=sleeps.append,
        random_fn=lambda: random_value,
    )


def test_client_create_get_list_and_delete() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.method == "POST":
            return httpx.Response(201, json={"id": "pod123", "name": "safe"})
        if request.method == "GET" and request.url.path.endswith("/pod123"):
            return httpx.Response(200, json={"id": "pod123", "desiredStatus": "RUNNING"})
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "pod123"}])
        return httpx.Response(204)

    with RunPodClient("test-key", transport=httpx.MockTransport(handler)) as client:
        assert client.create_pod({"name": "safe"})["id"] == "pod123"
        assert client.get_pod("pod123") == {"id": "pod123", "desiredStatus": "RUNNING"}
        assert client.list_pods() == [{"id": "pod123"}]
        assert client.delete_pod("pod123") is True

    assert seen == [
        ("POST", "/v1/pods"),
        ("GET", "/v1/pods/pod123"),
        ("GET", "/v1/pods"),
        ("DELETE", "/v1/pods/pod123"),
    ]


def test_client_treats_404_as_idempotent_absence() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(404, json={"error": "gone"}))
    with RunPodClient("key", transport=transport) as client:
        assert client.get_pod("missing") is None
        assert client.delete_pod("missing") is False


def test_api_errors_redact_secrets() -> None:
    secret = "sensitive-value"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401,
            text=f"Bearer {secret}",
            request=request,
        )
    )
    with RunPodClient(secret, transport=transport) as client, pytest.raises(ApiError) as raised:
        client.list_pods()
    assert secret not in str(raised.value)
    assert "HTTP 401" in str(raised.value)


def test_network_errors_are_actionable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with (
        RunPodClient("key", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(NetworkError, match="connection refused"),
    ):
        client.list_pods()


def test_unexpected_json_shapes_fail_cleanly() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"not": "a list"}))
    with (
        RunPodClient("key", transport=transport) as client,
        pytest.raises(ApiError, match="unexpected response shape"),
    ):
        client.list_pods()


def test_object_response_invalid_json_and_shape_fail_cleanly() -> None:
    invalid_json = httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json"))
    with (
        RunPodClient("key", transport=invalid_json) as client,
        pytest.raises(ApiError, match="invalid JSON"),
    ):
        client.create_pod({})

    wrong_shape = httpx.MockTransport(lambda _request: httpx.Response(200, json=[]))
    with (
        RunPodClient("key", transport=wrong_shape) as client,
        pytest.raises(ApiError, match="unexpected response shape"),
    ):
        client.create_pod({})


def test_list_invalid_json_fails_cleanly() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json"))
    with (
        RunPodClient("key", transport=transport) as client,
        pytest.raises(ApiError, match="invalid JSON"),
    ):
        client.list_pods()


def test_429_is_retried_then_succeeds_for_create() -> None:
    handler, calls = _sequence(
        [httpx.Response(429), httpx.Response(429), httpx.Response(201, json={"id": "pod123"})]
    )
    sleeps: list[float] = []
    with _client(handler, sleeps, random_value=0.5) as client:
        assert client.create_pod({"name": "safe"}) == {"id": "pod123"}
    assert calls == ["POST", "POST", "POST"]
    assert sleeps == [0.5, 1.0]


def test_retry_after_seconds_is_honored_and_clamped() -> None:
    handler, _calls = _sequence(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(429, headers={"Retry-After": "3600"}),
            httpx.Response(200, json=[]),
        ]
    )
    sleeps: list[float] = []
    with _client(handler, sleeps, backoff_cap=30.0) as client:
        assert client.list_pods() == []
    assert sleeps == [7.0, 30.0]


def test_retry_after_http_date_is_honored() -> None:
    future = datetime.now(UTC) + timedelta(seconds=20)
    handler, _calls = _sequence(
        [
            httpx.Response(429, headers={"Retry-After": format_datetime(future, usegmt=True)}),
            httpx.Response(200, json=[]),
        ]
    )
    sleeps: list[float] = []
    with _client(handler, sleeps) as client:
        assert client.list_pods() == []
    assert len(sleeps) == 1
    assert 15.0 <= sleeps[0] <= 20.0


def test_parse_retry_after_formats() -> None:
    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after("12", now=now) == 12.0
    assert parse_retry_after("Tue, 27 Oct 2026 12:00:30 GMT", now=now) == 30.0
    assert parse_retry_after("Tue, 27 Oct 2026 11:59:00 GMT", now=now) == 0.0
    assert parse_retry_after("Tue, 27 Oct 2026 12:00:05 -0000", now=now) == 5.0
    assert parse_retry_after("soon", now=now) is None
    assert parse_retry_after("", now=now) is None
    assert parse_retry_after(None) is None


def test_exhausted_429_raises_redacted_rate_limit_error() -> None:
    secret = "sensitive-value"
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(429, text=f"Bearer {secret}", headers={"Retry-After": "2"})

    sleeps: list[float] = []
    client = RunPodClient(
        secret,
        transport=httpx.MockTransport(handler),
        max_retries=3,
        sleep=sleeps.append,
        random_fn=lambda: 1.0,
    )
    with client, pytest.raises(RateLimitError) as raised:
        client.list_pods()
    error = raised.value
    assert isinstance(error, ApiError)
    assert error.status_code == 429
    assert error.retry_after == 2.0
    assert error.exit_code == ExitCode.API
    assert "rate limit" in str(error)
    assert "after 4 attempt(s)" in str(error)
    assert secret not in str(error)
    assert len(calls) == 4
    assert sleeps == [2.0, 2.0, 2.0]


def test_max_retries_zero_disables_retries() -> None:
    handler, calls = _sequence([httpx.Response(429)])
    sleeps: list[float] = []
    with _client(handler, sleeps, max_retries=0) as client, pytest.raises(RateLimitError):
        client.list_pods()
    assert calls == ["GET"]
    assert sleeps == []


@pytest.mark.parametrize("status", [400, 401, 403, 409, 422])
def test_other_4xx_are_not_retried(status: int) -> None:
    handler, calls = _sequence([httpx.Response(status)])
    sleeps: list[float] = []
    with _client(handler, sleeps) as client, pytest.raises(ApiError) as raised:
        client.list_pods()
    assert not isinstance(raised.value, RateLimitError)
    assert raised.value.status_code == status
    assert calls == ["GET"]
    assert sleeps == []


def test_transient_5xx_retried_only_for_idempotent_methods() -> None:
    handler, calls = _sequence([httpx.Response(503), httpx.Response(204)])
    sleeps: list[float] = []
    with _client(handler, sleeps) as client:
        assert client.delete_pod("pod123") is True
    assert calls == ["DELETE", "DELETE"]

    handler, calls = _sequence([httpx.Response(502)])
    sleeps = []
    with _client(handler, sleeps) as client, pytest.raises(ApiError) as raised:
        client.create_pod({})
    assert raised.value.status_code == 502
    assert calls == ["POST"]
    assert sleeps == []


def test_backoff_grows_exponentially_and_caps() -> None:
    handler, _calls = _sequence([httpx.Response(429)] * 7)
    sleeps: list[float] = []
    with (
        _client(handler, sleeps, max_retries=6, backoff_base=1.0, backoff_cap=10.0) as client,
        pytest.raises(RateLimitError),
    ):
        client.list_pods()
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_backoff_uses_full_jitter() -> None:
    handler, _calls = _sequence([httpx.Response(429)] * 4)
    sleeps: list[float] = []
    with (
        _client(handler, sleeps, random_value=0.25, max_retries=3) as client,
        pytest.raises(RateLimitError),
    ):
        client.list_pods()
    assert sleeps == [0.25, 0.5, 1.0]


def test_invalid_retry_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        RunPodClient("key", max_retries=-1)
    with pytest.raises(ValueError, match="Backoff"):
        RunPodClient("key", backoff_cap=-1.0)

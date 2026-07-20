from __future__ import annotations

import httpx
import pytest

from runpod_vllm.errors import ApiError, NetworkError, ReadinessTimeout
from runpod_vllm.readiness import smoke_test_endpoint, wait_until_ready


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_readiness_succeeds_after_initial_failure() -> None:
    health_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal health_calls
        if request.url.path == "/health":
            health_calls += 1
            return httpx.Response(503 if health_calls == 1 else 200)
        return httpx.Response(
            503 if health_calls == 1 else 200, json={"data": [{"id": "org/model"}]}
        )

    clock = Clock()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = wait_until_ready(
            "https://pod.example",
            timeout=10,
            interval=1,
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

    assert result.model_ids == ("org/model",)
    assert result.attempts == 2
    assert result.elapsed_seconds == 1


def test_readiness_timeout_has_diagnostic() -> None:
    clock = Clock()
    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(ReadinessTimeout, match="health HTTP 503, models HTTP 503"),
    ):
        wait_until_ready(
            "https://pod.example",
            timeout=2,
            interval=1,
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )


def test_smoke_test_is_deterministic_and_uses_optional_bearer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer endpoint-secret"
        body = __import__("json").loads(request.content)
        assert body["temperature"] == 0
        assert body["seed"] == 0
        assert body["max_tokens"] == 4
        return httpx.Response(200, json={"choices": [{"message": {"content": "ready"}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = smoke_test_endpoint(
            "https://pod.example",
            model="org/model",
            bearer_token="endpoint-secret",
            client=client,
        )
    assert response["choices"]


def test_smoke_test_rejects_bad_response() -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
        ) as client,
        pytest.raises(ApiError, match="did not contain choices"),
    ):
        smoke_test_endpoint("https://pod.example", model="org/model", client=client)


def test_readiness_validates_timing_and_reports_empty_models() -> None:
    with pytest.raises(ValueError, match="positive"):
        wait_until_ready("https://pod.example", timeout=0)

    clock = Clock()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        return httpx.Response(200, json={"data": []})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ReadinessTimeout, match="no model IDs"),
    ):
        wait_until_ready(
            "https://pod.example",
            timeout=1,
            interval=1,
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )


def test_smoke_test_http_and_network_errors_are_translated() -> None:
    error_transport = httpx.MockTransport(
        lambda _request: httpx.Response(500, text="server failed")
    )
    with (
        httpx.Client(transport=error_transport) as client,
        pytest.raises(ApiError, match="HTTP 500"),
    ):
        smoke_test_endpoint("https://pod.example", model="org/model", client=client)

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(fail)) as client,
        pytest.raises(NetworkError, match="offline"),
    ):
        smoke_test_endpoint("https://pod.example", model="org/model", client=client)

"""Offline fault-injection suite for the full RunPod CLI lifecycle.

A fake RunPod REST API (httpx.MockTransport) injects faults into a real
``RunPodClient`` wired into the real CLI: rate limits with Retry-After,
ambiguous create responses, readiness polling and teardown retries.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_readiness import Clock
from typer.testing import CliRunner

from runpod_vllm.cli import app
from runpod_vllm.client import RunPodClient
from runpod_vllm.config import ApiVersion
from runpod_vllm.errors import ReadinessTimeout, StateError
from runpod_vllm.models import DeploymentState
from runpod_vllm.readiness import wait_until_ready
from runpod_vllm.state import save_state

runner = CliRunner()

_V1_URL = "https://rest.runpod.io/v1"


def _install_real_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleeps: list[float] | None = None,
) -> None:
    """Wire the real RunPodClient (with the fake transport) into the CLI."""

    def factory(api_key: str, *, base_url: str, api_version: ApiVersion) -> RunPodClient:
        kwargs: dict[str, Any] = {"transport": httpx.MockTransport(handler)}
        if sleeps is not None:
            kwargs.update(sleep=sleeps.append, random_fn=lambda: 1.0)
        return RunPodClient(api_key, base_url=base_url, api_version=api_version, **kwargs)

    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", factory)


def test_deploy_retries_rate_limited_create_against_fake_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    posts: list[dict[str, Any]] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts.append(_json_body(request))
            if len(posts) == 1:
                return httpx.Response(429, headers={"Retry-After": "3"})
            return httpx.Response(201, json={"id": "pod123", "name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler, sleeps=sleeps)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )

    assert result.exit_code == 0, result.output
    assert "Pod created: pod123" in result.output
    assert len(posts) == 2 and posts[0] == posts[1]
    assert sleeps == [3.0]
    assert state_path.exists()


def test_ambiguous_create_response_is_not_retried_and_warns_about_billable_pod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    posts: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts.append(_json_body(request))
            return httpx.Response(502, text="bad gateway")
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )

    assert result.exit_code == 6, result.output
    assert len(posts) == 1, "a billable POST must never be blindly retried"
    assert "billable" in result.output
    assert "runpod-vllm --api-version v1 list" in result.output
    assert "runpod-vllm --api-version v1 destroy --pod-id <POD-ID> --yes" in result.output
    assert not state_path.exists()


def test_create_timeout_warns_about_possible_billable_pod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.method)
        raise httpx.ReadTimeout("timed out", request=request)

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )

    assert result.exit_code == 5, result.output
    assert attempts == ["POST"]
    assert "billable" in result.output
    assert "runpod-vllm --api-version v1 list" in result.output
    assert not state_path.exists()


def test_create_2xx_invalid_json_warns_about_possible_billable_pod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, text="<html>not json</html>")
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )

    assert result.exit_code == 6, result.output
    assert "billable" in result.output
    assert "runpod-vllm --api-version v1 list" in result.output
    assert not state_path.exists()


def test_create_2xx_wrong_shape_warns_about_possible_billable_pod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=["unexpected", "array"])
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )

    assert result.exit_code == 6, result.output
    assert "billable" in result.output
    assert "runpod-vllm --api-version v1 list" in result.output
    assert not state_path.exists()


def test_create_missing_pod_id_warns_about_possible_billable_pod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )

    assert result.exit_code == 8, result.output
    assert "did not return a valid Pod ID" in result.output
    assert "billable" in result.output
    assert "runpod-vllm --api-version v1 list" in result.output
    assert not state_path.exists()


def test_create_guidance_preserves_v2_version_and_default_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(502, text="bad gateway")
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 6, result.output
    assert "runpod-vllm --api-version v2 list" in result.output
    assert "--api-url" not in result.output, "default v2 URL needs no explicit flag"


def test_create_guidance_preserves_custom_api_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_url = "https://api.example.com/v2"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "--api-url",
            custom_url,
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 8, result.output
    assert f"runpod-vllm --api-version v2 --api-url {custom_url} list" in result.output, (
        result.output
    )
    assert f"runpod-vllm --api-version v2 --api-url {custom_url} destroy" in result.output


def test_create_guidance_quotes_and_redacts_custom_api_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_url = "https://user:s3cret@proxy.example.com/v2?region=us&token=shh123&team=x"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "--api-url",
            custom_url,
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 8, result.output
    quoted = "'https://<redacted>@proxy.example.com/v2?region=us&token=<redacted>'"
    assert f"--api-url {quoted} list" in result.output, result.output
    assert f"--api-url {quoted} destroy" in result.output
    assert "s3cret" not in result.output
    assert "shh123" not in result.output
    assert "redacted placeholder and is not executable" in result.output, result.output
    assert "Re-enter the exact original --api-url" in result.output, result.output

    printed = re.search(r"runpod-vllm (.+?) list", result.output)
    assert printed is not None, result.output
    tokens = shlex.split(printed.group(1))
    assert tokens == [
        "--api-version",
        "v2",
        "--api-url",
        quoted.strip("'"),
    ], "the URL must survive as one shell argument"


def test_create_guidance_non_sensitive_custom_url_stays_exact_copy_paste(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_url = "https://proxy.example.com/v2?region=us&team=x"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "--api-url",
            custom_url,
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 8, result.output
    assert f"runpod-vllm --api-version v2 --api-url '{custom_url}' list" in result.output, (
        result.output
    )
    assert (
        f"runpod-vllm --api-version v2 --api-url '{custom_url}' destroy --pod-id <POD-ID> --yes"
        in result.output
    ), result.output
    assert "not executable" not in result.output, "a non-sensitive URL needs no placeholder note"
    assert "Re-enter the exact original --api-url" not in result.output

    printed = re.search(r"runpod-vllm (.+?) list", result.output)
    assert printed is not None, result.output
    tokens = shlex.split(printed.group(1))
    assert tokens == [
        "--api-version",
        "v2",
        "--api-url",
        custom_url,
    ], "the quoted URL must survive as one shell argument"


def test_create_guidance_redacted_url_note_covers_userinfo_and_query_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_url = "https://admin:p4ssw0rd@api.example.com/v1"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-url",
            custom_url,
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 8, result.output
    assert "admin" not in result.output, "userinfo must not leak into the guidance"
    assert "p4ssw0rd" not in result.output, "userinfo secret must not leak"
    assert "redacted placeholder and is not executable" in result.output, result.output
    assert "Re-enter the exact original --api-url" in result.output, result.output


def test_create_guidance_redacted_url_note_on_state_save_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_url = "https://api.example.com/v2?token=shh123&team=x"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"id": "pod123", "name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)

    def fail_save(_path: Path, _state: DeploymentState) -> None:
        raise StateError("disk full")

    monkeypatch.setattr("runpod_vllm.cli.save_state", fail_save)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "--api-url",
            custom_url,
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 8, result.output
    assert (
        "runpod-vllm --api-version v2 --api-url 'https://api.example.com/v2?token=<redacted>' destroy --pod-id pod123 --yes"
        in result.output
    ), result.output
    assert "shh123" not in result.output, "query secret must not leak"
    assert "redacted placeholder and is not executable" in result.output, result.output
    assert "Re-enter the exact original --api-url" in result.output, result.output


def test_create_guidance_non_sensitive_url_on_state_save_failure_is_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_url = "https://api.example.com/v2?region=us&team=x"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"id": "pod123", "name": "vllm-server"})
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)

    def fail_save(_path: Path, _state: DeploymentState) -> None:
        raise StateError("disk full")

    monkeypatch.setattr("runpod_vllm.cli.save_state", fail_save)
    state_path = tmp_path / "state.json"

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "--api-url",
            custom_url,
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )

    assert result.exit_code == 8, result.output
    assert (
        f"runpod-vllm --api-version v2 --api-url '{custom_url}' destroy --pod-id pod123 --yes"
        in result.output
    ), result.output
    assert "not executable" not in result.output, "a non-sensitive URL needs no placeholder note"
    assert "Re-enter the exact original --api-url" not in result.output


def test_full_v2_lifecycle_survives_injected_faults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    sleeps: list[float] = []
    deletes = 0
    deleted = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal deletes, deleted
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            return httpx.Response(
                201, json={"id": "pod_v2x", "name": "vllm-server", "status": "PROVISIONING"}
            )
        if request.method == "DELETE":
            deletes += 1
            if deletes == 1:
                return httpx.Response(503)
            deleted = True
            return httpx.Response(204)
        if request.method == "GET" and request.url.path.endswith("/pod_v2x"):
            if deleted:
                return httpx.Response(404, json={"detail": "No such Pod."})
            return httpx.Response(200, json=_v2_pod())
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler, sleeps=sleeps)
    state_path = tmp_path / "state.json"

    deploy = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "--api-version",
            "v2",
            "deploy",
            "--model",
            "org/model",
            "--yes",
        ],
    )
    assert deploy.exit_code == 0, deploy.output
    assert "Pod created: pod_v2x" in deploy.output

    status = runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert status.exit_code == 0, status.output
    assert "State: RUNNING" in status.output

    destroy = runner.invoke(app, ["--state-path", str(state_path), "destroy", "--yes"])
    assert destroy.exit_code == 0, destroy.output
    assert "verified absent: pod_v2x" in destroy.output
    assert deletes == 2, "the 503 DELETE must be retried exactly once"
    assert sleeps, "the retry backoff must use the injected sleeper, not real sleep"
    assert all(delay <= 2.0 for delay in sleeps), sleeps
    assert not state_path.exists()
    assert calls == [
        "POST /v2/pods",
        "GET /v2/pods/pod_v2x",
        "DELETE /v2/pods/pod_v2x",
        "DELETE /v2/pods/pod_v2x",
        "GET /v2/pods/pod_v2x",
    ]


def test_destroy_retries_rate_limited_delete_and_verifies_absence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    responses: list[httpx.Response] = [
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(204),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return responses.pop(0)
        return httpx.Response(404, json={"error": "gone"})

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"
    _save_state(state_path)

    result = runner.invoke(
        app,
        ["--state-path", str(state_path), "destroy", "--yes", "--verify-timeout", "0.2"],
    )

    assert result.exit_code == 0, result.output
    assert "verified absent: pod123" in result.output
    assert not responses, "the rate-limited DELETE must be retried"
    assert not state_path.exists()


def test_destroy_keeps_state_when_deletion_verification_times_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json=_v1_pod())

    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    _install_real_client(monkeypatch, handler)
    state_path = tmp_path / "state.json"
    _save_state(state_path)

    result = runner.invoke(
        app,
        [
            "--state-path",
            str(state_path),
            "destroy",
            "--yes",
            "--verify-timeout",
            "0.15",
            "--verify-interval",
            "0.1",
        ],
    )

    assert result.exit_code == 8, result.output
    assert "still present" in result.output
    assert "Local state was retained" in result.output
    assert state_path.exists()


def test_readiness_polls_through_network_faults_then_times_out_with_diagnostic() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(503)

    clock = Clock()
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ReadinessTimeout, match="was not ready after") as raised,
    ):
        wait_until_ready(
            "https://pod.example",
            timeout=2,
            interval=1,
            client=client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
    assert "attempts" in str(raised.value)
    assert calls >= 2, "a network fault on one poll must not stop readiness polling"


def _v1_pod() -> dict[str, Any]:
    return {"id": "pod123", "name": "vllm-server", "desiredStatus": "RUNNING"}


def _v2_pod() -> dict[str, Any]:
    return {"id": "pod_v2x", "name": "vllm-server", "status": "RUNNING", "gpu": {"count": 1}}


def _json_body(request: httpx.Request) -> dict[str, Any]:
    import json

    body = json.loads(request.content)
    assert isinstance(body, dict)
    return body


def _save_state(path: Path) -> None:
    save_state(
        path,
        DeploymentState.create(
            pod_id="pod123",
            pod_name="vllm-server",
            model="org/model",
            port=8000,
            api_url=_V1_URL,
        ),
    )

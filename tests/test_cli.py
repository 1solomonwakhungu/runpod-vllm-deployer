from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

from runpod_vllm.cli import app
from runpod_vllm.errors import StateError
from runpod_vllm.models import DeploymentState, ReadinessResult
from runpod_vllm.state import save_state

runner = CliRunner()


class FakeClient:
    created_payload: ClassVar[dict[str, Any] | None] = None
    pod: ClassVar[dict[str, Any] | None] = {
        "id": "pod123",
        "name": "test",
        "desiredStatus": "RUNNING",
    }
    delete_result: ClassVar[bool] = True
    pods: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, api_key: str, *, base_url: str) -> None:
        assert api_key == "test-api-key"
        assert base_url.startswith("https://")

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def create_pod(self, payload: dict[str, Any]) -> dict[str, Any]:
        type(self).created_payload = payload
        return {"id": "pod123", "name": "test"}

    def get_pod(self, _pod_id: str) -> dict[str, Any] | None:
        return type(self).pod

    def delete_pod(self, _pod_id: str) -> bool:
        type(self).pod = None
        return type(self).delete_result

    def list_pods(self) -> list[dict[str, Any]]:
        return type(self).pods


@pytest.fixture(autouse=True)
def reset_fake() -> None:
    FakeClient.created_payload = None
    FakeClient.pod = {"id": "pod123", "name": "test", "desiredStatus": "RUNNING"}
    FakeClient.delete_result = True
    FakeClient.pods = []


def test_plan_is_offline_and_redacts_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "never-print-this")
    result = runner.invoke(
        app,
        [
            "plan",
            "--model",
            "org/model",
            "--env",
            "SERVICE_TOKEN=also-secret",
            "--env",
            "LOG_LEVEL=debug-value",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "offline; no API call" in result.output
    assert "never-print-this" not in result.output
    assert "also-secret" not in result.output
    assert "debug-value" not in result.output
    assert result.output.count("<redacted>") >= 3


def test_deploy_confirmation_gate_makes_no_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    result = runner.invoke(
        app,
        ["--state-path", str(tmp_path / "state.json"), "deploy", "--model", "org/model"],
        input="n\n",
    )
    assert result.exit_code == 2
    assert "Deployment cancelled" in result.output
    assert FakeClient.created_payload is None


def test_deploy_success_saves_state_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    result = runner.invoke(
        app,
        ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert "Pod created: pod123" in result.output
    assert state_path.exists()
    assert FakeClient.created_payload is not None


def test_partial_deploy_failure_prints_exact_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")

    def fail_save(_path: Path, _state: DeploymentState) -> None:
        raise StateError("disk full")

    monkeypatch.setattr("runpod_vllm.cli.save_state", fail_save)
    result = runner.invoke(
        app,
        ["--state-path", str(tmp_path / "state.json"), "deploy", "--model", "org/model", "--yes"],
    )
    assert result.exit_code == 8
    assert "runpod-vllm destroy --pod-id pod123 --yes" in result.output
    assert "test-api-key" not in result.output


def test_status_list_and_destroy_idempotently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_path = tmp_path / "state.json"
    save_state(
        state_path,
        DeploymentState.create(
            pod_id="pod123",
            pod_name="test",
            model="org/model",
            port=8000,
            api_url="https://rest.runpod.io/v1",
        ),
    )
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")

    status_result = runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert status_result.exit_code == 0, status_result.output
    assert "State: RUNNING" in status_result.output
    assert "https://pod123-8000.proxy.runpod.net" in status_result.output

    FakeClient.pods = [
        {"id": "pod123", "name": "test", "desiredStatus": "RUNNING", "gpu": {"count": 1}},
        {"id": "old", "name": "old", "desiredStatus": "TERMINATED"},
    ]
    list_result = runner.invoke(app, ["list"])
    assert list_result.exit_code == 0, list_result.output
    assert "pod123\tRUNNING\t1\ttest" in list_result.output
    assert "old" not in list_result.output

    FakeClient.delete_result = False
    destroy_result = runner.invoke(
        app,
        ["--state-path", str(state_path), "destroy", "--yes"],
    )
    assert destroy_result.exit_code == 0, destroy_result.output
    assert "already absent" in destroy_result.output
    assert not state_path.exists()


def test_commands_require_credentials_without_exposing_env_file(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    save_state(
        state_path,
        DeploymentState.create(
            pod_id="pod123",
            pod_name="test",
            model="org/model",
            port=8000,
            api_url="https://rest.runpod.io/v1",
        ),
    )
    result = runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert result.exit_code == 4
    assert "RUNPOD_API_KEY is required" in result.output


def test_help_exposes_all_lifecycle_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("plan", "deploy", "status", "wait", "smoke-test", "destroy", "list"):
        assert command in result.output


def test_wait_and_smoke_test_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_wait(base_url: str, *, timeout: float, interval: float) -> ReadinessResult:
        assert base_url == "https://pod.example"
        assert timeout == 5
        assert interval == 1
        return ReadinessResult(base_url, ("org/model",), 2, 1.5)

    def fake_smoke(
        base_url: str,
        *,
        model: str,
        bearer_token: str | None,
        timeout: float,
    ) -> dict[str, Any]:
        assert (base_url, model, bearer_token, timeout) == (
            "https://pod.example",
            "org/model",
            "endpoint-key",
            10,
        )
        return {"choices": [{}], "usage": {"total_tokens": 5}}

    monkeypatch.setattr("runpod_vllm.cli.wait_until_ready", fake_wait)
    monkeypatch.setattr("runpod_vllm.cli.smoke_test_endpoint", fake_smoke)
    monkeypatch.setenv("VLLM_API_KEY", "endpoint-key")

    wait_result = runner.invoke(
        app,
        ["wait", "--base-url", "https://pod.example", "--timeout", "5", "--interval", "1"],
    )
    assert wait_result.exit_code == 0, wait_result.output
    assert "Ready after 1.5s and 2 attempts" in wait_result.output

    smoke_result = runner.invoke(
        app,
        [
            "smoke-test",
            "--base-url",
            "https://pod.example",
            "--model",
            "org/model",
            "--timeout",
            "10",
        ],
    )
    assert smoke_result.exit_code == 0, smoke_result.output
    assert '"total_tokens": 5' in smoke_result.output


def test_status_absent_list_empty_and_destroy_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_path = tmp_path / "state.json"
    save_state(
        state_path,
        DeploymentState.create(
            pod_id="pod123",
            pod_name="test",
            model="org/model",
            port=8000,
            api_url="https://rest.runpod.io/v1",
        ),
    )
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    FakeClient.pod = None

    status_result = runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert status_result.exit_code == 0
    assert "absent" in status_result.output

    list_result = runner.invoke(app, ["list"])
    assert list_result.exit_code == 0
    assert "No active GPU Pods" in list_result.output

    destroy_result = runner.invoke(
        app,
        ["--state-path", str(state_path), "destroy"],
        input="n\n",
    )
    assert destroy_result.exit_code == 2
    assert "Destroy cancelled" in destroy_result.output
    assert state_path.exists()


def test_deploy_rejects_existing_state_and_invalid_recovery_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    deploy_result = runner.invoke(
        app,
        ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"],
    )
    assert deploy_result.exit_code == 8
    assert "State already exists" in deploy_result.output

    destroy_result = runner.invoke(app, ["destroy", "--pod-id", "bad id", "--yes"])
    assert destroy_result.exit_code == 8
    assert "invalid format" in destroy_result.output

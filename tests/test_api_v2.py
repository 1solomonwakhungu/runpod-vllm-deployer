"""Offline tests for RunPod REST v2 support and version selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_cli import FakeClient
from typer.testing import CliRunner

from runpod_vllm.cli import app
from runpod_vllm.client import RunPodClient
from runpod_vllm.config import ApiVersion, DeploymentConfig
from runpod_vllm.errors import ApiError, ConfigurationError
from runpod_vllm.models import DeploymentState, normalize_pod
from runpod_vllm.payload import build_pod_payload
from runpod_vllm.state import load_state, save_state

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUNPOD_API_VERSION", raising=False)
    FakeClient.created_payload = None
    FakeClient.pod = {"id": "pod123", "name": "test", "desiredStatus": "RUNNING"}
    FakeClient.delete_result = True
    FakeClient.pods = []
    FakeClient.last_target = None


V1_ONLY_KEYS = {
    "imageName",
    "computeType",
    "gpuTypeIds",
    "gpuTypePriority",
    "gpuCount",
    "dataCenterPriority",
    "minVCPUPerGPU",
    "minRAMPerGPU",
    "containerDiskInGb",
    "volumeInGb",
    "volumeMountPath",
    "dockerEntrypoint",
    "dockerStartCmd",
    "cloudType",
    "interruptible",
    "supportPublicIp",
}


def v2_pod(pod_id: str, status: str = "RUNNING", *, gpu: bool = True) -> dict[str, Any]:
    pod: dict[str, Any] = {"id": pod_id, "name": f"name-{pod_id}", "status": status}
    if gpu:
        pod["gpu"] = {"id": "NVIDIA A40", "count": 2, "vcpuCount": 8, "memory": 32}
    else:
        pod["cpu"] = {"id": "cpu5c", "vcpuCount": 4, "memory": 8}
    return pod


def test_v2_client_paths_auth_and_envelopes() -> None:
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        assert request.url.host == "api.runpod.io"
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.method == "POST":
            assert json.loads(request.content)["image"] == "img:1"
            return httpx.Response(201, json=v2_pod("pod_abc123", "PROVISIONING"))
        if request.method == "GET" and request.url.path == "/v2/pods/pod_abc123":
            return httpx.Response(200, json=v2_pod("pod_abc123"))
        if request.method == "GET" and "cursor=next1" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "pods": [v2_pod("pod_b")],
                    "pagination": {"nextCursor": None, "hasNextPage": False},
                },
            )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "pods": [v2_pod("pod_a"), v2_pod("cpu_pod", gpu=False)],
                    "pagination": {"nextCursor": "next1", "hasNextPage": True},
                },
            )
        return httpx.Response(204)

    with RunPodClient(
        "test-key", api_version=ApiVersion.V2, transport=httpx.MockTransport(handler)
    ) as client:
        assert client.create_pod({"image": "img:1"})["id"] == "pod_abc123"
        pod = client.get_pod("pod_abc123")
        assert pod is not None and pod["status"] == "RUNNING"
        assert [p["id"] for p in client.list_pods()] == ["pod_a", "pod_b"]
        assert client.delete_pod("pod_abc123") is True

    assert seen == [
        ("POST", "/v2/pods", ""),
        ("GET", "/v2/pods/pod_abc123", ""),
        ("GET", "/v2/pods", ""),
        ("GET", "/v2/pods", "cursor=next1"),
        ("DELETE", "/v2/pods/pod_abc123", ""),
    ]


def test_v2_client_respects_explicit_base_url_and_problem_404() -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(f"{request.url.host}{request.url.path}")
        return httpx.Response(
            404, json={"title": "Not Found", "status": 404, "detail": "No such Pod."}
        )

    with RunPodClient(
        "key",
        base_url="https://proxy.example.test/v2/",
        api_version=ApiVersion.V2,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.get_pod("gone") is None
        assert client.delete_pod("gone") is False
    assert hosts == ["proxy.example.test/v2/pods/gone"] * 2


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ([], "unexpected response shape"),
        ({"pods": "nope"}, "unexpected response shape"),
        ({"pods": [1]}, "unexpected response shape"),
        ({"pods": [], "pagination": {"hasNextPage": True, "nextCursor": None}}, "cursor"),
    ],
)
def test_v2_list_rejects_bad_envelopes(body: object, message: str) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=body))
    with (
        RunPodClient("key", api_version=ApiVersion.V2, transport=transport) as client,
        pytest.raises(ApiError, match=message),
    ):
        client.list_pods()


def test_v2_list_stops_runaway_pagination() -> None:
    page = {"pods": [], "pagination": {"hasNextPage": True, "nextCursor": "again"}}
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=page))
    with (
        RunPodClient("key", api_version=ApiVersion.V2, transport=transport) as client,
        pytest.raises(ApiError, match="pages"),
    ):
        client.list_pods()


def test_v2_payload_matches_create_pod_request_schema() -> None:
    config = DeploymentConfig(
        model="org/model",
        gpu_count=2,
        tensor_parallel_size=2,
        data_centers=("US-TX-3",),
        environment={"HF_TOKEN": "secret"},
    )
    payload = build_pod_payload(config, ApiVersion.V2)
    assert not V1_ONLY_KEYS & payload.keys()
    assert payload["name"] == "vllm-server"
    assert payload["image"] == config.image
    assert payload["gpu"] == {
        "id": "NVIDIA A40",
        "count": 2,
        "minVcpuCountPerGpu": 4,
        "minRamPerGpu": 16,
    }
    assert payload["disk"] == 50
    assert payload["mounts"] == {"persistent": {"size": 40, "path": "/workspace"}}
    assert payload["ports"] == ["8000/http"]
    assert payload["entrypoint"][:3] == ["vllm", "serve", "org/model"]
    assert payload["cloud"] == "SECURE"
    assert payload["dataCenterIds"] == ["US-TX-3"]
    assert payload["env"] == {"HF_TOKEN": "secret"}


def test_v2_payload_volume_rules_and_v1_default_unchanged() -> None:
    no_volume = build_pod_payload(DeploymentConfig(model="org/model", volume_gb=0), ApiVersion.V2)
    assert "mounts" not in no_volume and "dataCenterIds" not in no_volume
    with pytest.raises(ConfigurationError, match="at least 10 GB"):
        build_pod_payload(DeploymentConfig(model="org/model", volume_gb=5), ApiVersion.V2)
    v1 = build_pod_payload(DeploymentConfig(model="org/model"))
    assert v1["imageName"] and v1["volumeInGb"] == 40 and "image" not in v1


def test_normalize_pod_for_both_versions() -> None:
    v1 = normalize_pod(
        {"id": "a", "name": "n", "desiredStatus": "EXITED", "gpuCount": 1}, ApiVersion.V1
    )
    assert (v1.pod_id, v1.name, v1.status, v1.gpu_count) == ("a", "n", "EXITED", 1)
    v2 = normalize_pod(v2_pod("b", "TERMINATED"), ApiVersion.V2)
    assert (v2.status, v2.gpu_count, v2.is_terminated) == ("TERMINATED", 2, True)
    # A v1-shaped field is ignored when reading a v2 response, and vice versa.
    assert normalize_pod({"desiredStatus": "RUNNING"}, ApiVersion.V2).status == "UNKNOWN"
    assert normalize_pod({"status": "RUNNING"}, ApiVersion.V1).status == "UNKNOWN"
    assert normalize_pod({"gpu": {"count": True}}, ApiVersion.V2).gpu_count is None


def test_state_records_version_and_reads_legacy_files(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "pod_id": "pod123",
                "pod_name": "n",
                "model": "org/model",
                "port": 8000,
                "api_url": "https://rest.runpod.io/v1",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    assert load_state(legacy).api_version is ApiVersion.V1

    current = tmp_path / "v2.json"
    state = DeploymentState.create(
        pod_id="pod_x",
        pod_name="n",
        model="org/model",
        port=8000,
        api_url="https://api.runpod.io/v2",
        api_version=ApiVersion.V2,
    )
    save_state(current, state)
    assert json.loads(current.read_text(encoding="utf-8"))["api_version"] == "v2"
    assert load_state(current) == state


def _save_v2_state(path: Path, api_url: str = "https://api.runpod.io/v2") -> None:
    save_state(
        path,
        DeploymentState.create(
            pod_id="pod123",
            pod_name="test",
            model="org/model",
            port=8000,
            api_url=api_url,
            api_version=ApiVersion.V2,
        ),
    )


def test_plan_selects_v2_payload_via_option_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["--api-version", "v2", "plan", "--model", "org/model"])
    assert result.exit_code == 0, result.output
    assert "REST v2" in result.output and '"image": ' in result.output
    assert '"imageName"' not in result.output

    monkeypatch.setenv("RUNPOD_API_VERSION", "V2")
    env_result = runner.invoke(app, ["plan", "--model", "org/model"])
    assert env_result.exit_code == 0, env_result.output
    assert '"gpu": {' in env_result.output

    monkeypatch.setenv("RUNPOD_API_VERSION", "v3")
    bad = runner.invoke(app, ["plan", "--model", "org/model"])
    assert bad.exit_code != 0


def test_default_plan_and_deploy_stay_on_v1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    state_path = tmp_path / "state.json"
    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert FakeClient.last_target == ("https://rest.runpod.io/v1", ApiVersion.V1)
    assert FakeClient.created_payload is not None and "imageName" in FakeClient.created_payload
    saved = load_state(state_path)
    assert (saved.api_version, saved.api_url) == (ApiVersion.V1, "https://rest.runpod.io/v1")


def test_v2_deploy_records_version_for_later_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
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
    assert result.exit_code == 0, result.output
    assert FakeClient.created_payload is not None and "image" in FakeClient.created_payload
    saved = load_state(state_path)
    assert (saved.api_version, saved.api_url) == (ApiVersion.V2, "https://api.runpod.io/v2")

    FakeClient.last_target = None
    FakeClient.pod = v2_pod("pod123", "STARTING")
    status = runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert status.exit_code == 0, status.output
    assert "State: STARTING" in status.output and "REST v2" in status.output
    assert FakeClient.last_target == ("https://api.runpod.io/v2", ApiVersion.V2)


def test_explicit_options_override_recorded_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    state_path = tmp_path / "state.json"
    _save_v2_state(state_path, api_url="https://custom.example.test/v2")

    runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert FakeClient.last_target == ("https://custom.example.test/v2", ApiVersion.V2)

    runner.invoke(
        app, ["--state-path", str(state_path), "--api-url", "https://other.test/v2", "status"]
    )
    assert FakeClient.last_target == ("https://other.test/v2", ApiVersion.V2)

    FakeClient.pod = {"id": "pod123", "desiredStatus": "RUNNING"}
    result = runner.invoke(app, ["--state-path", str(state_path), "--api-version", "v1", "status"])
    assert "State: RUNNING" in result.output
    assert FakeClient.last_target == ("https://rest.runpod.io/v1", ApiVersion.V1)


def test_v2_destroy_treats_terminated_as_absent_and_list_normalizes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")

    FakeClient.pods = [v2_pod("pod_live"), v2_pod("pod_dead", "TERMINATED")]
    listed = runner.invoke(app, ["--api-version", "v2", "list"])
    assert listed.exit_code == 0, listed.output
    assert "pod_live\tRUNNING\t2\tname-pod_live" in listed.output
    assert "pod_dead" not in listed.output

    state_path = tmp_path / "state.json"
    _save_v2_state(state_path)

    class TerminatedAfterDelete(FakeClient):
        def delete_pod(self, _pod_id: str) -> bool:
            type(self).pod = v2_pod("pod123", "TERMINATED")
            return True

    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", TerminatedAfterDelete)
    result = runner.invoke(
        app,
        ["--state-path", str(state_path), "destroy", "--yes", "--verify-timeout", "0.5"],
    )
    assert result.exit_code == 0, result.output
    assert "verified absent: pod123" in result.output
    assert TerminatedAfterDelete.last_target == ("https://api.runpod.io/v2", ApiVersion.V2)
    assert not state_path.exists()

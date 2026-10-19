from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from test_cli import FakeClient
from typer.testing import CliRunner

from runpod_vllm.cli import app
from runpod_vllm.config import V1_RETIREMENT_DATE, ApiVersion, default_api_version
from runpod_vllm.state import load_state

runner = CliRunner()
AFTER_RETIREMENT = date(2026, 11, 15)


def _set_today(monkeypatch: pytest.MonkeyPatch, today: date) -> None:
    monkeypatch.setattr("runpod_vllm.cli._today", lambda: today)


def test_default_version_flips_on_retirement_date() -> None:
    assert date(2026, 11, 15) == V1_RETIREMENT_DATE
    assert default_api_version(date(2026, 11, 14)) is ApiVersion.V1
    assert default_api_version(date(2026, 11, 15)) is ApiVersion.V2
    assert default_api_version(date(2027, 1, 1)) is ApiVersion.V2


def test_new_deployments_use_v2_after_retirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_today(monkeypatch, AFTER_RETIREMENT)
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    plan = runner.invoke(app, ["plan", "--model", "org/model"])
    assert plan.exit_code == 0, plan.output
    assert "REST v2" in plan.output and '"imageName"' not in plan.output

    state_path = tmp_path / "state.json"
    result = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert FakeClient.last_target == ("https://api.runpod.io/v2", ApiVersion.V2)
    saved = load_state(state_path)
    assert (saved.api_version, saved.api_url) == (ApiVersion.V2, "https://api.runpod.io/v2")


def test_v1_deployments_move_to_v2_after_retirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("runpod_vllm.cli.RunPodClient", FakeClient)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-api-key")
    state_path = tmp_path / "state.json"
    created = runner.invoke(
        app, ["--state-path", str(state_path), "deploy", "--model", "org/model", "--yes"]
    )
    assert created.exit_code == 0, created.output
    assert load_state(state_path).api_version is ApiVersion.V1

    _set_today(monkeypatch, AFTER_RETIREMENT)
    FakeClient.last_target = None
    FakeClient.pod = {"id": "pod123", "name": "vllm-server", "status": "RUNNING"}
    status = runner.invoke(app, ["--state-path", str(state_path), "status"])
    assert status.exit_code == 0, status.output
    assert FakeClient.last_target == ("https://api.runpod.io/v2", ApiVersion.V2)

    runner.invoke(app, ["--state-path", str(state_path), "--api-version", "v1", "status"])
    assert FakeClient.last_target == ("https://rest.runpod.io/v1", ApiVersion.V1)

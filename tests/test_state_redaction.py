from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from runpod_vllm.errors import StateError
from runpod_vllm.models import DeploymentState
from runpod_vllm.redaction import (
    REDACTED,
    redact_deployment_plan,
    redact_mapping,
    redact_text,
    redact_url,
)
from runpod_vllm.state import load_state, remove_state, save_state


def sample_state() -> DeploymentState:
    return DeploymentState.create(
        pod_id="podabc123",
        pod_name="test-pod",
        model="org/model",
        port=8000,
        api_url="https://rest.runpod.io/v1",
    )


def test_state_round_trip_is_atomic_and_restrictive(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state.json"
    save_state(path, sample_state())

    assert load_state(path).pod_id == "podabc123"
    assert not list(path.parent.glob(f".{path.name}.*"))
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    remove_state(path)
    assert not path.exists()
    remove_state(path)


def test_invalid_or_missing_state_is_actionable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(StateError, match="No deployment state"):
        load_state(missing)
    missing.write_text(json.dumps({"pod_id": "only-one-field"}))
    with pytest.raises(StateError, match="Invalid deployment state"):
        load_state(missing)


def test_redaction_covers_nested_secrets_bearer_and_query() -> None:
    data = {
        "Authorization": "Bearer top-secret",
        "env": {"HF_TOKEN": "hidden", "LOG_LEVEL": "info"},
        "items": [{"api_key": "hidden-again"}],
    }
    redacted = redact_mapping(data)
    assert redacted["Authorization"] == REDACTED
    assert redacted["env"]["HF_TOKEN"] == REDACTED
    assert redacted["env"]["LOG_LEVEL"] == "info"
    assert "top-secret" not in redact_text("Authorization: Bearer top-secret")
    assert "json-secret" not in redact_text('{"token":"json-secret"}')
    assert redact_url("https://example.test/path?token=abc&safe=yes").endswith(
        "token=%3Credacted%3E&safe=yes"
    )


def test_deployment_plan_redacts_every_container_environment_value() -> None:
    redacted = redact_deployment_plan({"env": {"LOG_LEVEL": "debug", "SERVICE_URL": "private"}})
    assert redacted["env"] == {"LOG_LEVEL": REDACTED, "SERVICE_URL": REDACTED}

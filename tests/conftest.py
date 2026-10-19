from __future__ import annotations

import os
from datetime import date

import pytest


@pytest.fixture(autouse=True)
def clear_secret_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("RUNPOD_API_KEY", "HF_TOKEN", "VLLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert all(key not in os.environ for key in ("RUNPOD_API_KEY", "HF_TOKEN", "VLLM_API_KEY"))


@pytest.fixture(autouse=True)
def freeze_before_v1_retirement(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep default-version tests stable across RunPod's v1 retirement date.
    monkeypatch.setattr("runpod_vllm.cli._today", lambda: date(2026, 10, 1))

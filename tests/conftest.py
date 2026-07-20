from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def clear_secret_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("RUNPOD_API_KEY", "HF_TOKEN", "VLLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert all(key not in os.environ for key in ("RUNPOD_API_KEY", "HF_TOKEN", "VLLM_API_KEY"))

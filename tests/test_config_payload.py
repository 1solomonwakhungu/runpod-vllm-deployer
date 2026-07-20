from __future__ import annotations

from pathlib import Path

import pytest

from runpod_vllm.config import (
    DeploymentConfig,
    get_secret,
    load_env_file,
    parse_env_pairs,
    sanitize_name,
)
from runpod_vllm.errors import AuthenticationError, ConfigurationError
from runpod_vllm.payload import build_pod_payload, build_vllm_command


def test_payload_uses_current_rest_fields_and_vllm_options() -> None:
    config = DeploymentConfig(
        model="org/model-name",
        name="  My Safe Pod! ",
        gpu="H100",
        gpu_count=2,
        tensor_parallel_size=2,
        data_centers=("US-IL-1",),
        revision="abc123",
        max_model_len=32768,
        dtype="bfloat16",
        quantization="gptq",
        kv_cache_dtype="fp8",
        trust_remote_code=True,
        reasoning_parser="qwen3",
        environment={"HF_TOKEN": "private-value", "LOG_LEVEL": "info"},
    )

    payload = build_pod_payload(config)

    assert payload["name"] == "my-safe-pod"
    assert payload["gpuTypeIds"] == ["NVIDIA H100 80GB HBM3"]
    assert payload["dataCenterIds"] == ["US-IL-1"]
    assert payload["dataCenterPriority"] == "custom"
    assert payload["minVCPUPerGPU"] == 4
    assert payload["minRAMPerGPU"] == 16
    assert payload["dockerEntrypoint"] == []
    assert payload["ports"] == ["8000/http"]
    command = payload["dockerStartCmd"]
    assert command[:3] == ["vllm", "serve", "org/model-name"]
    assert "--revision" in command
    assert "--trust-remote-code" in command
    assert command[command.index("--tensor-parallel-size") + 1] == "2"


@pytest.mark.parametrize("gpu", ["A40", "L40S", "A100", "H100", "H200", "B200"])
def test_required_gpu_profiles_validate(gpu: str) -> None:
    assert DeploymentConfig(model="org/model", gpu=gpu).validated().gpu_type_id.startswith("NVIDIA")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"model": "bad model"}, "model ID"),
        ({"model": "ok/model", "gpu_count": 0}, "GPU count"),
        ({"model": "ok/model", "tensor_parallel_size": 2}, "Tensor parallel"),
        ({"model": "ok/model", "volume_gb": -1}, "volume"),
        ({"model": "ok/model", "port": 80}, "Port"),
        ({"model": "ok/model", "cloud_type": "OTHER"}, "Cloud type"),
        ({"model": "ok/model", "data_centers": ("not-a-dc",)}, "data center"),
        ({"model": "ok/model", "image": "vllm/vllm-openai:latest"}, "non-latest"),
    ],
)
def test_validation_rejects_unsafe_values(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        DeploymentConfig(**kwargs).validated()  # type: ignore[arg-type]


def test_name_and_environment_sanitization() -> None:
    assert sanitize_name("Client / Model ++ 2026") == "client-model-2026"
    assert parse_env_pairs(["LOG_LEVEL=debug", "EMPTY="]) == {
        "LOG_LEVEL": "debug",
        "EMPTY": "",
    }
    with pytest.raises(ConfigurationError, match="KEY=VALUE"):
        parse_env_pairs(["MISSING"])
    with pytest.raises(ConfigurationError, match="Invalid environment"):
        parse_env_pairs(["BAD-NAME=value"])


def test_command_omits_optional_flags_by_default() -> None:
    command = build_vllm_command(DeploymentConfig(model="org/model"))
    assert "--revision" not in command
    assert "--quantization" not in command
    assert "--trust-remote-code" not in command


def test_env_file_parsing_and_secret_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "selected.env"
    path.write_text(
        "# comment\nexport RUNPOD_API_KEY='file-key'\nHF_TOKEN=\"hf-value\"\nEMPTY=\n",
        encoding="utf-8",
    )
    values = load_env_file(path)
    assert values == {"RUNPOD_API_KEY": "file-key", "HF_TOKEN": "hf-value", "EMPTY": ""}
    assert load_env_file(None) == {}
    assert get_secret("RUNPOD_API_KEY", values) == "file-key"
    monkeypatch.setenv("RUNPOD_API_KEY", "process-key")
    assert get_secret("RUNPOD_API_KEY", values) == "process-key"


def test_env_file_errors_are_safe(tmp_path: Path) -> None:
    path = tmp_path / "bad.env"
    path.write_text("NOT AN ASSIGNMENT\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="line 1"):
        load_env_file(path)
    with pytest.raises(ConfigurationError, match="Could not read"):
        load_env_file(path.parent / "missing.env")
    with pytest.raises(AuthenticationError, match="MISSING_SECRET is required"):
        get_secret("MISSING_SECRET", {}, required=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"revision": "bad revision"},
        {"gpu": "T4"},
        {"gpu_count": 3, "tensor_parallel_size": 2},
        {"container_disk_gb": 9},
        {"min_vcpu_per_gpu": 0},
        {"min_ram_per_gpu": 0},
        {"max_model_len": 128},
        {"gpu_memory_utilization": 1.0},
        {"dtype": "int8"},
        {"kv_cache_dtype": "float64"},
    ],
)
def test_remaining_validation_boundaries(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigurationError):
        DeploymentConfig(model="org/model", **kwargs).validated()  # type: ignore[arg-type]


def test_empty_name_and_newline_environment_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="at least one"):
        sanitize_name("!!!")
    with pytest.raises(ConfigurationError, match="newlines"):
        parse_env_pairs(["VALUE=one\ntwo"])

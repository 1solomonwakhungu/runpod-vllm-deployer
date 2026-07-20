"""Deployment configuration, validation, and environment loading."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from runpod_vllm.errors import AuthenticationError, ConfigurationError

DEFAULT_IMAGE = "vllm/vllm-openai:v0.19.1"
DEFAULT_API_URL = "https://rest.runpod.io/v1"
DEFAULT_STATE_PATH = Path(".runpod-vllm-state.json")

GPU_PROFILES: dict[str, str] = {
    "A40": "NVIDIA A40",
    "L40S": "NVIDIA L40S",
    "A100": "NVIDIA A100-SXM4-80GB",
    "H100": "NVIDIA H100 80GB HBM3",
    "H200": "NVIDIA H200",
    "B200": "NVIDIA B200",
}

_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?$")
_REVISION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_DATA_CENTER_PATTERN = re.compile(r"^[A-Z]{2,3}-[A-Z0-9]{2,4}-[0-9]{1,2}$")
_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def sanitize_name(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    if not sanitized:
        raise ConfigurationError("Pod name must contain at least one letter or number.")
    return sanitized[:63].rstrip("-")


def parse_env_pairs(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ConfigurationError(f"Environment value must use KEY=VALUE syntax: {item!r}")
        key, value = item.split("=", 1)
        if not _ENV_KEY_PATTERN.fullmatch(key):
            raise ConfigurationError(f"Invalid environment variable name: {key!r}")
        if "\n" in value or "\r" in value:
            raise ConfigurationError(f"Environment value for {key} cannot contain newlines.")
        parsed[key] = value
    return parsed


def load_env_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError(f"Could not read env file {path}: {exc.strerror}") from exc
    values: dict[str, str] = {}
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(f"Invalid env file entry at line {line_number}.")
        key, value = line.split("=", 1)
        key = key.strip()
        if not _ENV_KEY_PATTERN.fullmatch(key):
            raise ConfigurationError(f"Invalid env file key at line {line_number}.")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def get_secret(name: str, env_file_values: dict[str, str], *, required: bool = False) -> str | None:
    value = os.environ.get(name) or env_file_values.get(name)
    if required and not value:
        raise AuthenticationError(
            f"{name} is required. Set it in the environment or pass --env-file PATH."
        )
    return value


@dataclass(frozen=True)
class DeploymentConfig:
    model: str
    name: str = "vllm-server"
    gpu: str = "A40"
    gpu_count: int = 1
    tensor_parallel_size: int = 1
    container_disk_gb: int = 50
    volume_gb: int = 40
    min_vcpu_per_gpu: int = 4
    min_ram_per_gpu: int = 16
    max_model_len: int = 8192
    gpu_memory_utilization: float = 0.90
    dtype: str = "auto"
    quantization: str | None = None
    kv_cache_dtype: str = "auto"
    revision: str | None = None
    trust_remote_code: bool = False
    reasoning_parser: str | None = None
    image: str = DEFAULT_IMAGE
    cloud_type: str = "SECURE"
    data_centers: tuple[str, ...] = ()
    port: int = 8000
    environment: dict[str, str] = field(default_factory=dict)

    def validated(self) -> DeploymentConfig:
        if not _MODEL_PATTERN.fullmatch(self.model):
            raise ConfigurationError("Model must be a valid Hugging Face model ID.")
        if self.revision and not _REVISION_PATTERN.fullmatch(self.revision):
            raise ConfigurationError("Revision contains unsupported characters.")
        if self.gpu not in GPU_PROFILES:
            choices = ", ".join(GPU_PROFILES)
            raise ConfigurationError(
                f"Unsupported GPU profile {self.gpu!r}. Choose from: {choices}."
            )
        if not 1 <= self.gpu_count <= 8:
            raise ConfigurationError("GPU count must be between 1 and 8.")
        if not 1 <= self.tensor_parallel_size <= self.gpu_count:
            raise ConfigurationError("Tensor parallel size must be between 1 and GPU count.")
        if self.gpu_count % self.tensor_parallel_size != 0:
            raise ConfigurationError("GPU count must be divisible by tensor parallel size.")
        if not 10 <= self.container_disk_gb <= 4096:
            raise ConfigurationError("Container disk must be between 10 and 4096 GB.")
        if not 0 <= self.volume_gb <= 4096:
            raise ConfigurationError("Pod volume must be between 0 and 4096 GB.")
        if not 1 <= self.min_vcpu_per_gpu <= 128:
            raise ConfigurationError("Minimum vCPU per GPU must be between 1 and 128.")
        if not 1 <= self.min_ram_per_gpu <= 2048:
            raise ConfigurationError("Minimum RAM per GPU must be between 1 and 2048 GB.")
        if not 256 <= self.max_model_len <= 1_048_576:
            raise ConfigurationError("Maximum model length must be between 256 and 1048576.")
        if not 0.1 <= self.gpu_memory_utilization <= 0.99:
            raise ConfigurationError("GPU memory utilization must be between 0.1 and 0.99.")
        if self.dtype not in {"auto", "bfloat16", "float16", "float32"}:
            raise ConfigurationError("dtype must be auto, bfloat16, float16, or float32.")
        if self.kv_cache_dtype not in {"auto", "fp8", "fp8_e4m3", "fp8_e5m2"}:
            raise ConfigurationError("KV cache dtype is not supported.")
        if not 1024 <= self.port <= 65535:
            raise ConfigurationError("Port must be between 1024 and 65535.")
        if self.cloud_type not in {"SECURE", "COMMUNITY"}:
            raise ConfigurationError("Cloud type must be SECURE or COMMUNITY.")
        invalid_centers = [dc for dc in self.data_centers if not _DATA_CENTER_PATTERN.fullmatch(dc)]
        if invalid_centers:
            raise ConfigurationError(f"Invalid data center ID: {invalid_centers[0]!r}")
        if not self.image or ":" not in self.image or self.image.endswith(":latest"):
            raise ConfigurationError("Image must use an explicit non-latest tag.")
        sanitize_name(self.name)
        return self

    @property
    def pod_name(self) -> str:
        return sanitize_name(self.name)

    @property
    def gpu_type_id(self) -> str:
        return GPU_PROFILES[self.gpu]

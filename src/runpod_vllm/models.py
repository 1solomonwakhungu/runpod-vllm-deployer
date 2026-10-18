"""Typed domain models."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from runpod_vllm.config import ApiVersion


@dataclass(frozen=True)
class DeploymentState:
    pod_id: str
    pod_name: str
    model: str
    port: int
    api_url: str
    created_at: str
    # State files written before REST v2 support lack this field; they were v1 deployments.
    api_version: ApiVersion = ApiVersion.V1

    @classmethod
    def create(
        cls,
        *,
        pod_id: str,
        pod_name: str,
        model: str,
        port: int,
        api_url: str,
        api_version: ApiVersion = ApiVersion.V1,
    ) -> "DeploymentState":
        return cls(
            pod_id=pod_id,
            pod_name=pod_name,
            model=model,
            port=port,
            api_url=api_url,
            created_at=datetime.now(UTC).isoformat(),
            api_version=api_version,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeploymentState":
        return cls(
            pod_id=str(data["pod_id"]),
            pod_name=str(data["pod_name"]),
            model=str(data["model"]),
            port=int(data["port"]),
            api_url=str(data["api_url"]),
            created_at=str(data["created_at"]),
            api_version=ApiVersion(str(data.get("api_version", ApiVersion.V1.value))),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["api_version"] = self.api_version.value
        return data

    @property
    def proxy_url(self) -> str:
        # RunPod HTTP proxy convention. The v2 Pod schema does not document a proxy URL
        # field, so the same format is assumed for Pods created through REST v2.
        return f"https://{self.pod_id}-{self.port}.proxy.runpod.net"

    @property
    def health_url(self) -> str:
        return f"{self.proxy_url}/health"

    @property
    def models_url(self) -> str:
        return f"{self.proxy_url}/v1/models"


@dataclass(frozen=True)
class PodInfo:
    """Version-independent view of a RunPod Pod response."""

    pod_id: str
    name: str
    status: str
    gpu_count: int | None

    @property
    def is_terminated(self) -> bool:
        return self.status == "TERMINATED"


def normalize_pod(raw: dict[str, Any], api_version: ApiVersion) -> PodInfo:
    """Map a v1 or v2 Pod object onto :class:`PodInfo`.

    v1 reports lifecycle as ``desiredStatus`` and GPUs as ``gpuCount`` or ``gpu.count``.
    v2 (``Pod`` in https://api.runpod.io/v2/openapi.json) reports ``status`` with values
    PROVISIONING, STARTING, RUNNING, EXITED, ERROR, TERMINATED and GPUs as ``gpu.count``.
    """
    gpu_value = raw.get("gpu")
    gpu: dict[str, Any] = gpu_value if isinstance(gpu_value, dict) else {}
    if api_version is ApiVersion.V2:
        status = raw.get("status")
        count = gpu.get("count")
    else:
        status = raw.get("desiredStatus")
        count = gpu.get("count", raw.get("gpuCount"))
    return PodInfo(
        pod_id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        status=str(status) if status else "UNKNOWN",
        gpu_count=count if isinstance(count, int) and not isinstance(count, bool) else None,
    )


@dataclass(frozen=True)
class ReadinessResult:
    base_url: str
    model_ids: tuple[str, ...]
    attempts: int
    elapsed_seconds: float

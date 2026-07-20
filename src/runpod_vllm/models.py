"""Typed domain models."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DeploymentState:
    pod_id: str
    pod_name: str
    model: str
    port: int
    api_url: str
    created_at: str

    @classmethod
    def create(
        cls, *, pod_id: str, pod_name: str, model: str, port: int, api_url: str
    ) -> "DeploymentState":
        return cls(
            pod_id=pod_id,
            pod_name=pod_name,
            model=model,
            port=port,
            api_url=api_url,
            created_at=datetime.now(UTC).isoformat(),
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
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def proxy_url(self) -> str:
        return f"https://{self.pod_id}-{self.port}.proxy.runpod.net"

    @property
    def health_url(self) -> str:
        return f"{self.proxy_url}/health"

    @property
    def models_url(self) -> str:
        return f"{self.proxy_url}/v1/models"


@dataclass(frozen=True)
class ReadinessResult:
    base_url: str
    model_ids: tuple[str, ...]
    attempts: int
    elapsed_seconds: float

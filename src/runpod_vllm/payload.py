"""RunPod Pod payload and vLLM command construction."""

from typing import Any

from runpod_vllm.config import ApiVersion, DeploymentConfig
from runpod_vllm.errors import ConfigurationError

VOLUME_MOUNT_PATH = "/workspace"
# REST v2 PersistentMount.size has "minimum": 10 in https://api.runpod.io/v2/openapi.json.
V2_MIN_PERSISTENT_VOLUME_GB = 10


def build_vllm_command(config: DeploymentConfig) -> list[str]:
    command = [
        "vllm",
        "serve",
        config.model,
        "--host",
        "0.0.0.0",
        "--port",
        str(config.port),
        "--tensor-parallel-size",
        str(config.tensor_parallel_size),
        "--max-model-len",
        str(config.max_model_len),
        "--gpu-memory-utilization",
        str(config.gpu_memory_utilization),
        "--dtype",
        config.dtype,
        "--kv-cache-dtype",
        config.kv_cache_dtype,
    ]
    if config.revision:
        command.extend(["--revision", config.revision])
    if config.quantization:
        command.extend(["--quantization", config.quantization])
    if config.trust_remote_code:
        command.append("--trust-remote-code")
    if config.reasoning_parser:
        command.extend(["--reasoning-parser", config.reasoning_parser])
    return command


def build_pod_payload(
    config: DeploymentConfig, api_version: ApiVersion = ApiVersion.V1
) -> dict[str, Any]:
    """Build the create-Pod request body for the selected RunPod REST API version."""
    config.validated()
    if api_version is ApiVersion.V2:
        return _build_v2_payload(config)
    return _build_v1_payload(config)


def _build_v1_payload(config: DeploymentConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": config.pod_name,
        "imageName": config.image,
        "computeType": "GPU",
        "gpuTypeIds": [config.gpu_type_id],
        "gpuTypePriority": "availability",
        "gpuCount": config.gpu_count,
        "dataCenterPriority": "custom" if config.data_centers else "availability",
        "minVCPUPerGPU": config.min_vcpu_per_gpu,
        "minRAMPerGPU": config.min_ram_per_gpu,
        "containerDiskInGb": config.container_disk_gb,
        "volumeInGb": config.volume_gb,
        "volumeMountPath": VOLUME_MOUNT_PATH,
        "ports": [f"{config.port}/http"],
        "dockerEntrypoint": [],
        "dockerStartCmd": build_vllm_command(config),
        "env": dict(config.environment),
        "cloudType": config.cloud_type,
        "interruptible": False,
        "supportPublicIp": True,
    }
    if config.data_centers:
        payload["dataCenterIds"] = list(config.data_centers)
    return payload


def _build_v2_payload(config: DeploymentConfig) -> dict[str, Any]:
    """Map the deployment onto the REST v2 ``CreatePodRequest`` schema.

    Verified against https://api.runpod.io/v2/openapi.json (CreatePodRequest,
    CreateGpuConfig, BaseContainerConfig, Mounts, PersistentMount). The schema sets
    ``unevaluatedProperties: false``, so v1-only keys (computeType, gpuTypePriority,
    dataCenterPriority, interruptible, supportPublicIp, volumeMountPath) must not be
    sent. v2 has no equivalent for them, including no spot/interruptible option.
    """
    if 0 < config.volume_gb < V2_MIN_PERSISTENT_VOLUME_GB:
        raise ConfigurationError(
            "RunPod REST v2 requires a Pod volume of 0 or at least "
            f"{V2_MIN_PERSISTENT_VOLUME_GB} GB."
        )
    payload: dict[str, Any] = {
        "name": config.pod_name,
        "image": config.image,
        "gpu": {
            "id": config.gpu_type_id,
            "count": config.gpu_count,
            "minVcpuCountPerGpu": config.min_vcpu_per_gpu,
            "minRamPerGpu": config.min_ram_per_gpu,
        },
        "disk": config.container_disk_gb,
        "ports": [f"{config.port}/http"],
        # v1 sent dockerEntrypoint=[] plus the full command as dockerStartCmd. The v2
        # schema documents an empty entrypoint as "clear", which is ambiguous on create,
        # so the complete exec-form command is sent as the entrypoint override instead.
        "entrypoint": build_vllm_command(config),
        "env": dict(config.environment),
        "cloud": config.cloud_type,
    }
    if config.volume_gb:
        payload["mounts"] = {"persistent": {"size": config.volume_gb, "path": VOLUME_MOUNT_PATH}}
    if config.data_centers:
        # The v2 schema calls dataCenterIds "preferred data centers for placement"; it
        # does not say whether placement is restricted to them (v1 used priority=custom).
        payload["dataCenterIds"] = list(config.data_centers)
    return payload

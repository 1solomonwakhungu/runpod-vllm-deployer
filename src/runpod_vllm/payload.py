"""RunPod Pod payload and vLLM command construction."""

from typing import Any

from runpod_vllm.config import DeploymentConfig


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


def build_pod_payload(config: DeploymentConfig) -> dict[str, Any]:
    config.validated()
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
        "volumeMountPath": "/workspace",
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

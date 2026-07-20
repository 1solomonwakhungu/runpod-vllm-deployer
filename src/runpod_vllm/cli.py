"""Typer command-line interface."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import typer

from runpod_vllm import __version__
from runpod_vllm.client import RunPodClient
from runpod_vllm.config import (
    DEFAULT_API_URL,
    DEFAULT_IMAGE,
    DEFAULT_STATE_PATH,
    DeploymentConfig,
    get_secret,
    load_env_file,
    parse_env_pairs,
)
from runpod_vllm.errors import ExitCode, RunpodVllmError, StateError
from runpod_vllm.models import DeploymentState
from runpod_vllm.payload import build_pod_payload
from runpod_vllm.readiness import smoke_test_endpoint, wait_until_ready
from runpod_vllm.redaction import redact_deployment_plan
from runpod_vllm.state import load_state, remove_state, save_state

app = typer.Typer(
    name="runpod-vllm",
    help="Safely deploy and tear down OpenAI-compatible vLLM servers on RunPod.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

_POD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


@dataclass(frozen=True)
class CliContext:
    state_path: Path
    env_file: Path | None
    api_url: str

    def env_values(self) -> dict[str, str]:
        return load_env_file(self.env_file)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    state_path: Path = typer.Option(
        DEFAULT_STATE_PATH,
        "--state-path",
        help="Path to local teardown state.",
        dir_okay=False,
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help="Optional env file containing RUNPOD_API_KEY and HF_TOKEN.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    api_url: str = typer.Option(DEFAULT_API_URL, "--api-url", help="RunPod REST API base URL."),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Configure paths shared by lifecycle commands."""
    del version
    ctx.obj = CliContext(state_path=state_path, env_file=env_file, api_url=api_url)


def _context(ctx: typer.Context) -> CliContext:
    value = ctx.find_root().obj
    if not isinstance(value, CliContext):
        raise RuntimeError("CLI context was not initialized")
    return value


def _fail(exc: RunpodVllmError) -> NoReturn:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=int(exc.exit_code))


def _config(
    *,
    model: str,
    name: str,
    gpu: str,
    gpu_count: int,
    tensor_parallel_size: int,
    container_disk_gb: int,
    volume_gb: int,
    min_vcpu_per_gpu: int,
    min_ram_per_gpu: int,
    max_model_len: int,
    gpu_memory_utilization: float,
    dtype: str,
    quantization: str | None,
    kv_cache_dtype: str,
    revision: str | None,
    trust_remote_code: bool,
    reasoning_parser: str | None,
    image: str,
    cloud_type: str,
    data_center: list[str] | None,
    port: int,
    environment: list[str] | None,
    hf_token: str | None,
) -> DeploymentConfig:
    env = parse_env_pairs(environment or [])
    if hf_token:
        env["HF_TOKEN"] = hf_token
    return DeploymentConfig(
        model=model,
        name=name,
        gpu=gpu.upper(),
        gpu_count=gpu_count,
        tensor_parallel_size=tensor_parallel_size,
        container_disk_gb=container_disk_gb,
        volume_gb=volume_gb,
        min_vcpu_per_gpu=min_vcpu_per_gpu,
        min_ram_per_gpu=min_ram_per_gpu,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        dtype=dtype.lower(),
        quantization=quantization,
        kv_cache_dtype=kv_cache_dtype.lower(),
        revision=revision,
        trust_remote_code=trust_remote_code,
        reasoning_parser=reasoning_parser,
        image=image,
        cloud_type=cloud_type.upper(),
        data_centers=tuple(data_center or []),
        port=port,
        environment=env,
    ).validated()


def _common_config(
    ctx: typer.Context,
    model: str,
    name: str,
    gpu: str,
    gpu_count: int,
    tensor_parallel_size: int,
    container_disk_gb: int,
    volume_gb: int,
    min_vcpu_per_gpu: int,
    min_ram_per_gpu: int,
    max_model_len: int,
    gpu_memory_utilization: float,
    dtype: str,
    quantization: str | None,
    kv_cache_dtype: str,
    revision: str | None,
    trust_remote_code: bool,
    reasoning_parser: str | None,
    image: str,
    cloud_type: str,
    data_center: list[str] | None,
    port: int,
    environment: list[str] | None,
) -> DeploymentConfig:
    cli_context = _context(ctx)
    values = cli_context.env_values()
    hf_token = get_secret("HF_TOKEN", values)
    return _config(
        model=model,
        name=name,
        gpu=gpu,
        gpu_count=gpu_count,
        tensor_parallel_size=tensor_parallel_size,
        container_disk_gb=container_disk_gb,
        volume_gb=volume_gb,
        min_vcpu_per_gpu=min_vcpu_per_gpu,
        min_ram_per_gpu=min_ram_per_gpu,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        dtype=dtype,
        quantization=quantization,
        kv_cache_dtype=kv_cache_dtype,
        revision=revision,
        trust_remote_code=trust_remote_code,
        reasoning_parser=reasoning_parser,
        image=image,
        cloud_type=cloud_type,
        data_center=data_center,
        port=port,
        environment=environment,
        hf_token=hf_token,
    )


@app.command()
def plan(
    ctx: typer.Context,
    model: str = typer.Option(..., "--model", help="Hugging Face model ID."),
    name: str = typer.Option("vllm-server", "--name", help="Pod name; sanitized before use."),
    gpu: str = typer.Option(
        "A40", "--gpu", help="GPU profile: A40, L40S, A100, H100, H200, or B200."
    ),
    gpu_count: int = typer.Option(1, "--gpu-count", min=1, max=8, help="Number of GPUs."),
    tensor_parallel_size: int = typer.Option(
        1, "--tensor-parallel-size", min=1, max=8, help="vLLM tensor parallel size."
    ),
    container_disk_gb: int = typer.Option(
        50, "--container-disk-gb", help="Ephemeral container disk size in GB."
    ),
    volume_gb: int = typer.Option(40, "--volume-gb", help="Pod volume size in GB."),
    min_vcpu_per_gpu: int = typer.Option(4, "--min-vcpu-per-gpu", help="Minimum vCPUs per GPU."),
    min_ram_per_gpu: int = typer.Option(
        16, "--min-ram-per-gpu", help="Minimum host RAM per GPU in GB."
    ),
    max_model_len: int = typer.Option(
        8192, "--max-model-len", help="Maximum model context length."
    ),
    gpu_memory_utilization: float = typer.Option(
        0.90, "--gpu-memory-utilization", help="Fraction of GPU memory available to vLLM."
    ),
    dtype: str = typer.Option(
        "auto", "--dtype", help="vLLM dtype: auto, bfloat16, float16, or float32."
    ),
    quantization: str | None = typer.Option(
        None, "--quantization", help="Optional vLLM quantization method."
    ),
    kv_cache_dtype: str = typer.Option(
        "auto", "--kv-cache-dtype", help="KV cache dtype: auto, fp8, fp8_e4m3, or fp8_e5m2."
    ),
    revision: str | None = typer.Option(
        None, "--revision", help="Optional model revision or commit."
    ),
    trust_remote_code: bool = typer.Option(
        False, "--trust-remote-code", help="Allow model repository code execution."
    ),
    reasoning_parser: str | None = typer.Option(
        None, "--reasoning-parser", help="Optional vLLM reasoning parser name."
    ),
    image: str = typer.Option(DEFAULT_IMAGE, "--image", help="Pinned vLLM container image."),
    cloud_type: str = typer.Option(
        "SECURE", "--cloud-type", help="RunPod cloud type: SECURE or COMMUNITY."
    ),
    data_center: list[str] | None = typer.Option(
        None, "--data-center", help="Allowed RunPod data center ID; repeatable."
    ),
    port: int = typer.Option(8000, "--port", help="HTTP port exposed by vLLM."),
    environment: list[str] | None = typer.Option(
        None, "--env", help="Container KEY=VALUE; repeatable and redacted in plans."
    ),
) -> None:
    """Validate inputs and print a redacted plan without network access."""
    try:
        config = _common_config(
            ctx,
            model,
            name,
            gpu,
            gpu_count,
            tensor_parallel_size,
            container_disk_gb,
            volume_gb,
            min_vcpu_per_gpu,
            min_ram_per_gpu,
            max_model_len,
            gpu_memory_utilization,
            dtype,
            quantization,
            kv_cache_dtype,
            revision,
            trust_remote_code,
            reasoning_parser,
            image,
            cloud_type,
            data_center,
            port,
            environment,
        )
        typer.echo("Deployment plan (offline; no API call)")
        typer.echo(
            json.dumps(redact_deployment_plan(build_pod_payload(config)), indent=2, sort_keys=True)
        )
    except RunpodVllmError as exc:
        _fail(exc)


@app.command()
def deploy(
    ctx: typer.Context,
    model: str = typer.Option(..., "--model", help="Hugging Face model ID."),
    name: str = typer.Option("vllm-server", "--name", help="Pod name; sanitized before use."),
    gpu: str = typer.Option(
        "A40", "--gpu", help="GPU profile: A40, L40S, A100, H100, H200, or B200."
    ),
    gpu_count: int = typer.Option(1, "--gpu-count", min=1, max=8, help="Number of GPUs."),
    tensor_parallel_size: int = typer.Option(
        1, "--tensor-parallel-size", min=1, max=8, help="vLLM tensor parallel size."
    ),
    container_disk_gb: int = typer.Option(
        50, "--container-disk-gb", help="Ephemeral container disk size in GB."
    ),
    volume_gb: int = typer.Option(40, "--volume-gb", help="Pod volume size in GB."),
    min_vcpu_per_gpu: int = typer.Option(4, "--min-vcpu-per-gpu", help="Minimum vCPUs per GPU."),
    min_ram_per_gpu: int = typer.Option(
        16, "--min-ram-per-gpu", help="Minimum host RAM per GPU in GB."
    ),
    max_model_len: int = typer.Option(
        8192, "--max-model-len", help="Maximum model context length."
    ),
    gpu_memory_utilization: float = typer.Option(
        0.90, "--gpu-memory-utilization", help="Fraction of GPU memory available to vLLM."
    ),
    dtype: str = typer.Option(
        "auto", "--dtype", help="vLLM dtype: auto, bfloat16, float16, or float32."
    ),
    quantization: str | None = typer.Option(
        None, "--quantization", help="Optional vLLM quantization method."
    ),
    kv_cache_dtype: str = typer.Option(
        "auto", "--kv-cache-dtype", help="KV cache dtype: auto, fp8, fp8_e4m3, or fp8_e5m2."
    ),
    revision: str | None = typer.Option(
        None, "--revision", help="Optional model revision or commit."
    ),
    trust_remote_code: bool = typer.Option(
        False, "--trust-remote-code", help="Allow model repository code execution."
    ),
    reasoning_parser: str | None = typer.Option(
        None, "--reasoning-parser", help="Optional vLLM reasoning parser name."
    ),
    image: str = typer.Option(DEFAULT_IMAGE, "--image", help="Pinned vLLM container image."),
    cloud_type: str = typer.Option(
        "SECURE", "--cloud-type", help="RunPod cloud type: SECURE or COMMUNITY."
    ),
    data_center: list[str] | None = typer.Option(
        None, "--data-center", help="Allowed RunPod data center ID; repeatable."
    ),
    port: int = typer.Option(8000, "--port", help="HTTP port exposed by vLLM."),
    environment: list[str] | None = typer.Option(
        None, "--env", help="Container KEY=VALUE; repeatable and never printed unredacted."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the billable-operation confirmation."
    ),
) -> None:
    """Create a billable RunPod GPU Pod and save teardown state."""
    cli_context = _context(ctx)
    try:
        config = _common_config(
            ctx,
            model,
            name,
            gpu,
            gpu_count,
            tensor_parallel_size,
            container_disk_gb,
            volume_gb,
            min_vcpu_per_gpu,
            min_ram_per_gpu,
            max_model_len,
            gpu_memory_utilization,
            dtype,
            quantization,
            kv_cache_dtype,
            revision,
            trust_remote_code,
            reasoning_parser,
            image,
            cloud_type,
            data_center,
            port,
            environment,
        )
        if cli_context.state_path.exists():
            raise StateError(
                f"State already exists at {cli_context.state_path}. Destroy that Pod or choose another --state-path."
            )
        if not yes and not typer.confirm("Create a billable RunPod GPU Pod?"):
            typer.echo("Deployment cancelled.")
            raise typer.Exit(code=int(ExitCode.USAGE))
        api_key = get_secret("RUNPOD_API_KEY", cli_context.env_values(), required=True)
        assert api_key is not None
        with RunPodClient(api_key, base_url=cli_context.api_url) as client:
            created = client.create_pod(build_pod_payload(config))
        pod_id = created.get("id")
        if not isinstance(pod_id, str) or not _POD_ID_PATTERN.fullmatch(pod_id):
            raise StateError("RunPod created a Pod but did not return a valid Pod ID.")
        state = DeploymentState.create(
            pod_id=pod_id,
            pod_name=str(created.get("name") or config.pod_name),
            model=config.model,
            port=config.port,
            api_url=cli_context.api_url,
        )
        try:
            save_state(cli_context.state_path, state)
        except StateError:
            typer.echo(
                f"Critical: Pod {pod_id} was created but state could not be saved. "
                f"Clean it up with: runpod-vllm destroy --pod-id {pod_id} --yes",
                err=True,
            )
            raise
        typer.echo(f"Pod created: {pod_id}")
        typer.echo(f"Teardown state: {cli_context.state_path}")
        typer.echo(f"Next: runpod-vllm wait --state-path {cli_context.state_path}")
    except RunpodVllmError as exc:
        _fail(exc)


@app.command()
def status(ctx: typer.Context) -> None:
    """Inspect the recorded Pod and show lifecycle state and URLs."""
    cli_context = _context(ctx)
    try:
        state = load_state(cli_context.state_path)
        api_key = get_secret("RUNPOD_API_KEY", cli_context.env_values(), required=True)
        assert api_key is not None
        with RunPodClient(api_key, base_url=cli_context.api_url) as client:
            pod = client.get_pod(state.pod_id)
        if pod is None:
            typer.echo(f"Pod {state.pod_id}: absent")
            return
        typer.echo(f"Pod: {state.pod_id}")
        typer.echo(f"Name: {pod.get('name', state.pod_name)}")
        typer.echo(f"State: {pod.get('desiredStatus', 'UNKNOWN')}")
        typer.echo(f"Base URL: {state.proxy_url}")
        typer.echo(f"Health: {state.health_url}")
        typer.echo(f"Models: {state.models_url}")
    except RunpodVllmError as exc:
        _fail(exc)


@app.command(name="wait")
def wait_command(
    ctx: typer.Context,
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override the recorded proxy base URL."
    ),
    timeout: float = typer.Option(900.0, "--timeout", min=0.1, help="Maximum wait in seconds."),
    interval: float = typer.Option(5.0, "--interval", min=0.1, help="Polling interval in seconds."),
) -> None:
    """Wait for /health and /v1/models readiness."""
    try:
        selected_url = base_url
        if selected_url is None:
            selected_url = load_state(_context(ctx).state_path).proxy_url
        result = wait_until_ready(selected_url, timeout=timeout, interval=interval)
        typer.echo(
            f"Ready after {result.elapsed_seconds:.1f}s and {result.attempts} attempts: "
            f"{', '.join(result.model_ids)}"
        )
    except RunpodVllmError as exc:
        _fail(exc)


@app.command(name="smoke-test")
def smoke_test_command(
    ctx: typer.Context,
    base_url: str | None = typer.Option(
        None, "--base-url", help="Override the recorded proxy base URL."
    ),
    model: str | None = typer.Option(None, "--model", help="Override the recorded model ID."),
    bearer_token_env: str = typer.Option(
        "VLLM_API_KEY",
        "--bearer-token-env",
        help="Environment variable containing an optional endpoint bearer token.",
    ),
    timeout: float = typer.Option(30.0, "--timeout", min=0.1, help="Request timeout in seconds."),
) -> None:
    """Send a small deterministic OpenAI-compatible chat request."""
    try:
        cli_context = _context(ctx)
        state = None
        if base_url is None or model is None:
            state = load_state(cli_context.state_path)
        selected_url = base_url or (state.proxy_url if state else "")
        selected_model = model or (state.model if state else "")
        token = os.environ.get(bearer_token_env) or cli_context.env_values().get(bearer_token_env)
        data = smoke_test_endpoint(
            selected_url,
            model=selected_model,
            bearer_token=token,
            timeout=timeout,
        )
        usage = data.get("usage")
        suffix = f" Usage: {json.dumps(usage, sort_keys=True)}" if isinstance(usage, dict) else ""
        typer.echo(f"Smoke test passed.{suffix}")
    except RunpodVllmError as exc:
        _fail(exc)


@app.command()
def destroy(
    ctx: typer.Context,
    pod_id: str | None = typer.Option(
        None, "--pod-id", help="Explicit Pod ID for state-recovery cleanup."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the destructive-operation confirmation."
    ),
    verify_timeout: float = typer.Option(
        60.0, "--verify-timeout", min=0.1, help="Maximum deletion verification time in seconds."
    ),
    verify_interval: float = typer.Option(
        2.0, "--verify-interval", min=0.1, help="Deletion verification interval in seconds."
    ),
) -> None:
    """Terminate a Pod, verify absence, and remove matching local state."""
    cli_context = _context(ctx)
    try:
        state: DeploymentState | None = None
        if pod_id is None:
            state = load_state(cli_context.state_path)
            selected_id = state.pod_id
        else:
            if not _POD_ID_PATTERN.fullmatch(pod_id):
                raise StateError("Explicit Pod ID has an invalid format.")
            selected_id = pod_id
            try:
                candidate = load_state(cli_context.state_path)
                if candidate.pod_id == selected_id:
                    state = candidate
            except StateError:
                pass
        if not yes and not typer.confirm(f"Permanently terminate Pod {selected_id}?"):
            typer.echo("Destroy cancelled.")
            raise typer.Exit(code=int(ExitCode.USAGE))
        api_key = get_secret("RUNPOD_API_KEY", cli_context.env_values(), required=True)
        assert api_key is not None
        with RunPodClient(api_key, base_url=cli_context.api_url) as client:
            requested = client.delete_pod(selected_id)
            deadline = time.monotonic() + verify_timeout
            while client.get_pod(selected_id) is not None:
                if time.monotonic() >= deadline:
                    raise StateError(
                        f"Pod {selected_id} is still present after {verify_timeout:.1f}s. "
                        "Local state was retained."
                    )
                time.sleep(verify_interval)
        if state is not None:
            remove_state(cli_context.state_path)
        action = "Termination requested" if requested else "Pod was already absent"
        typer.echo(f"{action}; verified absent: {selected_id}")
        if state is not None:
            typer.echo(f"Removed local state: {cli_context.state_path}")
    except RunpodVllmError as exc:
        _fail(exc)


@app.command(name="list")
def list_command(ctx: typer.Context) -> None:
    """List active RunPod GPU Pods without changing resources."""
    cli_context = _context(ctx)
    try:
        api_key = get_secret("RUNPOD_API_KEY", cli_context.env_values(), required=True)
        assert api_key is not None
        with RunPodClient(api_key, base_url=cli_context.api_url) as client:
            pods = client.list_pods()
        active = [pod for pod in pods if pod.get("desiredStatus") != "TERMINATED"]
        if not active:
            typer.echo("No active GPU Pods found.")
            return
        typer.echo("ID\tSTATUS\tGPUS\tNAME")
        for pod in active:
            gpu_value = pod.get("gpu")
            gpu: dict[str, Any] = gpu_value if isinstance(gpu_value, dict) else {}
            count = gpu.get("count", pod.get("gpuCount", "?"))
            typer.echo(
                f"{pod.get('id', '?')}\t{pod.get('desiredStatus', 'UNKNOWN')}\t"
                f"{count}\t{pod.get('name', '')}"
            )
    except RunpodVllmError as exc:
        _fail(exc)

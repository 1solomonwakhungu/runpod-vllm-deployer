# Configuration

Global options must appear before the command:

| Option | Default | Purpose |
| --- | --- | --- |
| `--state-path PATH` | `.runpod-vllm-state.json` | Select local teardown state |
| `--env-file PATH` | None | Load secrets from a user-selected env file |
| `--api-url TEXT` | Version default, or the URL in state | Override the RunPod REST base URL |
| `--api-version [v1\|v2]` | `v2` (since 2026-11-15), or the version in state | Select the RunPod REST API version; also read from `RUNPOD_API_VERSION` |
| `--version` | | Print the CLI version |

## RunPod REST API version

RunPod retired REST API v1 (`https://rest.runpod.io/v1`) on **2026-11-15**. REST API v2 (`https://api.runpod.io/v2`) is the current surface and the automatic CLI default from 2026-11-15 onward, so no `--api-version` flag is needed for normal RunPod usage. You can still set `--api-version` or `RUNPOD_API_VERSION` explicitly when targeting a custom endpoint:

```bash
runpod-vllm plan --model Qwen/Qwen3-8B
export RUNPOD_API_VERSION=v2   # explicit opt-in if desired
```

How the version and URL are chosen:

1. An explicit `--api-version` (or `RUNPOD_API_VERSION`) wins. An explicit `--api-url` wins for the URL.
2. Otherwise `status` and `destroy` reuse the `api_version` and `api_url` recorded in the state file by `deploy`. Since 2026-11-15, legacy v1 state files (including files written without `api_version`) automatically move to v2 using the same Pod ID.
3. Otherwise new deployments use v2 and `https://api.runpod.io/v2` (before 2026-11-15 the automatic default was v1 and `https://rest.runpod.io/v1`).

`--api-url` does not change the version. Pair a custom v2-compatible URL with `--api-version v2`.

Both versions send `RUNPOD_API_KEY` as a Bearer token in the `Authorization` header. The v2 create body differs from v1:

| Setting | v1 field | v2 field |
| --- | --- | --- |
| Image | `imageName` | `image` |
| GPU type and count | `gpuTypeIds`, `gpuCount` | `gpu.id`, `gpu.count` |
| Host vCPU and RAM minimums | `minVCPUPerGPU`, `minRAMPerGPU` | `gpu.minVcpuCountPerGpu`, `gpu.minRamPerGpu` |
| Container disk | `containerDiskInGb` | `disk` |
| Pod volume | `volumeInGb`, `volumeMountPath` | `mounts.persistent.size`, `mounts.persistent.path` |
| Command | `dockerEntrypoint: []`, `dockerStartCmd` | `entrypoint` (full exec-form command) |
| Cloud | `cloudType` | `cloud` |
| Data centers | `dataCenterIds` with `dataCenterPriority: custom` | `dataCenterIds` (documented as preferred placement) |

v2 rejects unknown fields, so the v1-only `computeType`, `gpuTypePriority`, `dataCenterPriority`, `interruptible`, and `supportPublicIp` are not sent. v2 requires `--volume-gb` to be `0` or at least `10`. Run `plan` with each version to compare the exact payloads.

## Deployment options

`plan` and `deploy` accept the same configuration options. `deploy` additionally accepts `--yes` or `-y`.

| Option | Default | Notes |
| --- | --- | --- |
| `--model TEXT` | Required | Hugging Face `ORG/MODEL` or model ID |
| `--name TEXT` | `vllm-server` | Lowercased and sanitized to 63 characters |
| `--gpu TEXT` | `A40` | `RTX4090`, `RTX5090`, `A6000`, `A40`, `L40S`, `A100`, `H100`, `H200`, or `B200` |
| `--gpu-type-id TEXT` | None | Raw RunPod GPU type ID (2 to 120 printable ASCII characters, no leading/trailing whitespace); overrides `--gpu` |
| `--gpu-count INTEGER` | `1` | From 1 through 8 |
| `--tensor-parallel-size INTEGER` | `1` | Must divide GPU count |
| `--container-disk-gb INTEGER` | `50` | Ephemeral container disk |
| `--volume-gb INTEGER` | `40` | Pod volume mounted at `/workspace`; `0` disables it |
| `--min-vcpu-per-gpu INTEGER` | `4` | RunPod placement minimum |
| `--min-ram-per-gpu INTEGER` | `16` | Host RAM placement minimum in GB |
| `--max-model-len INTEGER` | `8192` | vLLM context length |
| `--gpu-memory-utilization FLOAT` | `0.9` | Allowed range is 0.1 through 0.99 |
| `--dtype TEXT` | `auto` | `auto`, `bfloat16`, `float16`, or `float32` |
| `--quantization TEXT` | None | vLLM quantization method, such as `gptq` or `awq` |
| `--kv-cache-dtype TEXT` | `auto` | `auto`, `fp8`, `fp8_e4m3`, or `fp8_e5m2` |
| `--revision TEXT` | None | Model branch, tag, or commit |
| `--trust-remote-code` | Off | Execute code supplied by the model repository |
| `--reasoning-parser TEXT` | None | vLLM reasoning parser name |
| `--image TEXT` | `vllm/vllm-openai:v0.19.1` | Must use an explicit tag other than `latest` |
| `--cloud-type TEXT` | `SECURE` | `SECURE` or `COMMUNITY` |
| `--data-center TEXT` | None | Repeat to restrict placement |
| `--port INTEGER` | `8000` | vLLM HTTP port, from 1024 through 65535 |
| `--env TEXT` | None | Repeatable `KEY=VALUE` container setting |

Use `runpod-vllm plan --help` and `runpod-vllm deploy --help` as the executable reference.

## Credentials

- `RUNPOD_API_KEY` is required for RunPod API commands.
- `HF_TOKEN` is optional and passed to the Pod only when present.
- `VLLM_API_KEY` is optional and used by `smoke-test` as endpoint bearer authentication.

The process environment takes precedence over the selected env file. Never put a secret directly in `--env`; command histories and process listings can retain it. Prefer the credential environment variables.

## Data center selection

Repeat `--data-center` to provide an ordered allowlist:

```bash
runpod-vllm plan \
  --model ORG/MODEL \
  --data-center US-IL-1 \
  --data-center US-TX-3
```

RunPod data center availability changes. Consult the current RunPod API documentation before restricting placement.

## GPU profiles and custom GPU type IDs

Built-in `--gpu` profiles map short names to RunPod GPU type IDs:

| Profile | RunPod GPU type ID |
| --- | --- |
| `RTX4090` | `NVIDIA GeForce RTX 4090` |
| `RTX5090` | `NVIDIA GeForce RTX 5090` |
| `A6000` | `NVIDIA RTX A6000` |
| `A40` | `NVIDIA A40` |
| `L40S` | `NVIDIA L40S` |
| `A100` | `NVIDIA A100-SXM4-80GB` |
| `H100` | `NVIDIA H100 80GB HBM3` |
| `H200` | `NVIDIA H200` |
| `B200` | `NVIDIA B200` |

To target any other RunPod GPU SKU without waiting for a new built-in profile, pass `--gpu-type-id` with the exact RunPod GPU type identifier:

```bash
runpod-vllm plan \
  --model ORG/MODEL \
  --gpu-type-id "NVIDIA RTX PRO 6000"
```

`--gpu-type-id` overrides `--gpu` and is validated to 2 through 120 printable ASCII characters (`A-Z`, `a-z`, `0-9`, spaces, and `._+()/-`) with no leading or trailing whitespace.

## Model sizing

GPU profile support means the CLI knows the RunPod GPU type identifier. It is not a claim that a given checkpoint fits. Confirm weight size, quantization overhead, KV cache requirements, context length, dtype support, and tensor parallel requirements from primary model and vLLM documentation.

## OpenAI client output

When `wait` or `smoke-test` succeeds, the CLI prints the normalized OpenAI-compatible base URL (`.../v1`) along with a shell-quoted `export OPENAI_BASE_URL=...` snippet ready to copy into your terminal or OpenAI SDK configuration. If a custom `--base-url` contains embedded credentials (userinfo or sensitive query parameters), those values are redacted before printing and a note warns you to re-enter the original URL from your environment.

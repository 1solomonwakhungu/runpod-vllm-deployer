# Configuration

Global options must appear before the command:

| Option | Default | Purpose |
| --- | --- | --- |
| `--state-path PATH` | `.runpod-vllm-state.json` | Select local teardown state |
| `--env-file PATH` | None | Load secrets from a user-selected env file |
| `--api-url TEXT` | `https://rest.runpod.io/v1` | Override the RunPod REST base URL |
| `--version` | | Print the CLI version |

## Deployment options

`plan` and `deploy` accept the same configuration options. `deploy` additionally accepts `--yes` or `-y`.

| Option | Default | Notes |
| --- | --- | --- |
| `--model TEXT` | Required | Hugging Face `ORG/MODEL` or model ID |
| `--name TEXT` | `vllm-server` | Lowercased and sanitized to 63 characters |
| `--gpu TEXT` | `A40` | `A40`, `L40S`, `A100`, `H100`, `H200`, or `B200` |
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

## Model sizing

GPU profile support means the CLI knows the RunPod GPU type identifier. It is not a claim that a given checkpoint fits. Confirm weight size, quantization overhead, KV cache requirements, context length, dtype support, and tensor parallel requirements from primary model and vLLM documentation.

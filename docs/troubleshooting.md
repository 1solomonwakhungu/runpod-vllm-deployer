# Troubleshooting

## Authentication fails

Confirm `RUNPOD_API_KEY` is exported or present in the file selected by the global `--env-file PATH` option:

```bash
runpod-vllm --env-file .env list
```

The CLI never prints the value. Rotate a credential immediately if it was pasted into logs or committed.

## No GPU is available

RunPod capacity changes continuously. Try another supported `--gpu` profile, remove data center restrictions, or wait for inventory. Check live availability and price before accepting a different GPU.

## Pod exists but readiness times out

Run:

```bash
runpod-vllm --env-file .env status
runpod-vllm wait --timeout 1200 --interval 10
```

Then inspect Pod and container logs in the RunPod console. Typical causes include checkpoint download authentication, insufficient storage, incompatible image or model revisions, unsupported quantization, out-of-memory errors, and overly large context settings.

## Model does not fit

Reduce `--max-model-len`, choose an appropriate quantization, adjust `--dtype` or `--kv-cache-dtype`, increase GPU count with a compatible `--tensor-parallel-size`, or select a larger GPU. Treat all sizing guidance as approximate and verify against the exact checkpoint.

## Smoke test gets 401 or 403

If the endpoint requires bearer authentication, set `VLLM_API_KEY` or choose another variable:

```bash
runpod-vllm smoke-test --bearer-token-env MY_ENDPOINT_TOKEN
```

Do not put the token value directly in the command.

## State file is missing

If Pod creation succeeded but the state write failed, use the Pod ID printed by `deploy`:

```bash
runpod-vllm --env-file .env destroy --pod-id POD_ID --yes
```

If you no longer have that ID, use `runpod-vllm --env-file .env list`, identify the intended Pod carefully, then use the explicit cleanup command.

## Deletion verification times out

The CLI retains local state. Check `status`, review the RunPod console, and retry `destroy`. Do not delete the state file until the Pod is confirmed absent.

## RunPod REST v1 calls fail after retirement

RunPod retires REST API v1 on 2026-11-15. After that date v1 calls are expected to fail. Switch to v2:

```bash
runpod-vllm --api-version v2 plan --model Qwen/Qwen3-8B
export RUNPOD_API_VERSION=v2
```

A deployment created through v1 keeps `api_version: v1` in its state file. To inspect or destroy it after the retirement date, pass `--api-version v2` explicitly; the Pod ID is used unchanged. If v2 rejects a create request with HTTP 400 or 422, run `plan` with `--api-version v2` and compare the payload with [Configuration](configuration.md#runpod-rest-api-version). v2 requires `--volume-gb 0` or at least `10`.

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

## RunPod rate limit (HTTP 429)

From 2026-10-27, RunPod limits each account across all public APIs to 180 requests per minute, 3,600 per hour, and 43,200 per day. When RunPod answers HTTP 429, the client waits and retries the request up to 5 times. It honors the `Retry-After` header (seconds or an HTTP date, capped at 60 seconds) and otherwise uses exponential backoff with full jitter, starting at 1 second and capped at 60 seconds. Retrying `create` is safe because a 429 means RunPod rejected the request without creating a Pod.

GET and DELETE requests are also retried on HTTP 502, 503, and 504. Pod creation is not retried on those statuses, because the Pod may already exist; run `list` before trying again.

If every retry is rate limited, the command exits with code 6 and reports that the RunPod rate limit was hit. Wait a few minutes, then check whether other scripts or tools share the same API key and are using up its quota.

## RunPod REST v1 calls fail after retirement

RunPod retires REST API v1 on 2026-11-15. After that date v1 calls are expected to fail. The CLI switches its default to v2 on that date, so this only affects runs that force v1 with `--api-version v1` or `RUNPOD_API_VERSION=v1`. Remove that setting, or switch to v2 explicitly:

```bash
runpod-vllm --api-version v2 plan --model Qwen/Qwen3-8B
export RUNPOD_API_VERSION=v2
```

A deployment created through v1 keeps `api_version: v1` in its state file. From the retirement date, `status` and `destroy` use v2 for it automatically; the Pod ID is used unchanged. If v2 rejects a create request with HTTP 400 or 422, run `plan` with `--api-version v2` and compare the payload with [Configuration](configuration.md#runpod-rest-api-version). v2 requires `--volume-gb 0` or at least `10`.

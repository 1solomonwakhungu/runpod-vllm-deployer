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

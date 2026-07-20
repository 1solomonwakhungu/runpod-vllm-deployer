# Quickstart

This guide takes you from a clean checkout to a verified vLLM endpoint and a confirmed teardown.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
cp .env.example .env
```

Set `RUNPOD_API_KEY` in `.env`. Set `HF_TOKEN` only for a gated or authenticated model repository.

## Plan offline

```bash
runpod-vllm plan \
  --model ORG/MODEL \
  --name example-vllm \
  --gpu A40 \
  --max-model-len 8192
```

Planning validates input, redacts sensitive environment values, and performs no network call.

## Deploy

Warning: the next command creates a billable GPU Pod after confirmation.

```bash
runpod-vllm --env-file .env deploy \
  --model ORG/MODEL \
  --name example-vllm \
  --gpu A40 \
  --max-model-len 8192
```

The CLI saves `.runpod-vllm-state.json` immediately after receiving the Pod ID.

## Verify

```bash
runpod-vllm --env-file .env status
runpod-vllm wait --timeout 900 --interval 5
runpod-vllm smoke-test --timeout 30
```

If the endpoint uses its own bearer authentication, store that value in `VLLM_API_KEY`. Change the variable name with `--bearer-token-env NAME`.

## Destroy

```bash
runpod-vllm --env-file .env destroy
```

The command requests deletion, verifies absence, and removes local state. Confirm the result before closing your terminal.

Next: [configuration](configuration.md), [lifecycle safety](lifecycle.md), and [troubleshooting](troubleshooting.md).

#!/usr/bin/env bash
set -euo pipefail

# Safe placeholders only. Review the offline plan before the billable deploy.
runpod-vllm plan \
  --model ORG/MODEL \
  --name example-vllm \
  --gpu A40 \
  --max-model-len 8192 \
  --dtype auto \
  --kv-cache-dtype auto

# The following lifecycle commands require credentials in .env.
runpod-vllm --env-file .env deploy --model ORG/MODEL --gpu A40
runpod-vllm --env-file .env status
runpod-vllm wait --timeout 900
runpod-vllm smoke-test
runpod-vllm --env-file .env destroy

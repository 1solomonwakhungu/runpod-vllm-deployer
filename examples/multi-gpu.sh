#!/usr/bin/env bash
set -euo pipefail

# Planning remains offline. Verify that the exact checkpoint supports this setup.
runpod-vllm plan \
  --model ORG/MODEL \
  --gpu H100 \
  --gpu-count 2 \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --revision MODEL_REVISION \
  --quantization QUANTIZATION_METHOD

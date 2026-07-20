# Contributing

Thank you for improving RunPod vLLM Deployer.

## Development setup

```bash
git clone https://github.com/1solomonwakhungu/runpod-vllm-deployer.git
cd runpod-vllm-deployer
python3 -m venv .venv
source .venv/bin/activate
make setup
make check
```

All tests must remain offline. Use `httpx.MockTransport`, fixtures, or fakes for RunPod and vLLM behavior. Never use a real API key in tests, examples, issues, or pull requests.

## Pull requests

1. Keep changes focused and explain their safety impact.
2. Add or update tests for behavior changes.
3. Update command documentation when CLI help changes.
4. Run `make check`.
5. Confirm the diff contains no credentials, Pod IDs, private paths, or private URLs.

Use clear commit messages. Changes that weaken confirmation gates, teardown-state persistence, redaction, or offline testing need an explicit rationale and focused tests.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

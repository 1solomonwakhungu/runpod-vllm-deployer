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

Changes that weaken confirmation gates, teardown-state persistence, redaction, or offline testing need an explicit rationale and focused tests.

## Commit and pull request titles

Commit messages and pull request titles must follow [Conventional Commits](https://www.conventionalcommits.org/), for example `fix: retry readiness checks after a timeout`. Releases are automated, and the commit type decides the next version. Pull requests are squash-merged, so the pull request title becomes the commit on `main`.

| Type | Use for | Release |
| --- | --- | --- |
| `feat` | A new feature | Minor |
| `fix` | A bug fix | Patch |
| `perf` | A performance improvement | Patch |
| `docs` | Documentation only | None |
| `test` | Tests only | None |
| `refactor` | Restructuring without a behavior change | None |
| `style` | Formatting only | None |
| `build` | Build system or packaging | None |
| `ci` | Workflow changes | None |
| `chore` | Other maintenance | None |

Mark a breaking change with `!` after the type, for example `feat!: remove the --legacy flag`, or with a `BREAKING CHANGE:` footer. While the project is `0.x`, a breaking change bumps the minor version.

Do not edit the version, `CHANGELOG.md`, or tags by hand. See [RELEASING.md](RELEASING.md) for the full process.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

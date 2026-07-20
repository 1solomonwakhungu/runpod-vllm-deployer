# Security model

## Credential handling

The CLI reads `RUNPOD_API_KEY` and optional `HF_TOKEN` from the process environment or the exact file supplied with `--env-file`. It has no personal path fallback and does not search the filesystem for credentials.

The endpoint smoke test reads its optional bearer token from `VLLM_API_KEY` by default. Select another environment variable with `--bearer-token-env NAME`.

Secrets are never written to the local state file. Deployment plans recursively redact keys that look like authorization, token, secret, password, cookie, credential, or API key fields. Network diagnostics redact bearer values and sensitive query parameters.

Redaction is defense in depth, not permission to pass secrets on command lines. Shell history, process inspection, provider logs, model code, or container behavior can expose values before the CLI sees them.

## Trust boundaries

- RunPod receives the Pod configuration and any environment values sent during deployment.
- Hugging Face receives model download requests from the Pod.
- The configured container image executes with the Pod's filesystem and network access.
- A model repository can execute code when `--trust-remote-code` is enabled.
- The vLLM endpoint is reachable through the RunPod proxy URL unless you add endpoint authentication and network controls.

Review container tags and model revisions before use. Prefer immutable model commits. Enable `--trust-remote-code` only after auditing the repository.

## Local files

`.env` and default state files are ignored by Git. State is created with mode `0600` where supported. Directory permissions and backups remain the operator's responsibility.

## Static checks

CI scans tracked text for common credential assignments, private-path markers, and prohibited Unicode punctuation. It complements GitHub's platform security features but does not prove that a repository contains no secrets.

For vulnerability reporting, follow [SECURITY.md](../SECURITY.md).

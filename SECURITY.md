# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability.

Use the repository's private [GitHub Security Advisory reporting](https://github.com/1solomonwakhungu/runpod-vllm-deployer/security/advisories/new) channel. Include affected commands, impact, a minimal reproduction, and any suggested mitigation. Do not include real credentials, live Pod identifiers, or sensitive inference data.

The maintainer will acknowledge reports through the advisory thread and coordinate remediation there. No response-time or disclosure-timeline guarantee is made.

## Scope

Security-sensitive areas include credential handling, redaction, env-file parsing, state permissions, confirmation bypasses, RunPod API request construction, endpoint authentication, and dependency behavior.

This project does not independently provide compliance certification, data-retention guarantees, or infrastructure security guarantees. Operators remain responsible for their RunPod account, models, container images, network exposure, data, and provider configuration.

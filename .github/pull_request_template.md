## Summary

Describe the change and its user impact.

## Safety impact

Explain any effect on billing gates, teardown state, credentials, redaction, network access, or deletion behavior.

## Validation

- [ ] `make check` passes
- [ ] Tests use mocks or offline fixtures only
- [ ] Documentation matches actual CLI help
- [ ] The diff contains no credentials, private paths, Pod IDs, private URLs, or sensitive payloads
- [ ] No live RunPod resource was created or mutated while testing

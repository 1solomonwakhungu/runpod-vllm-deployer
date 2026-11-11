# Releasing

This guide is for maintainers. Contributors only need the commit rules in [CONTRIBUTING.md](CONTRIBUTING.md#commit-and-pull-request-titles).

## Overview

Releases are automated with [python-semantic-release](https://python-semantic-release.readthedocs.io/). The Release workflow (`.github/workflows/release.yml`) runs on every push to `main`, which in practice means after each merged pull request. It reads the commits since the last release tag and decides whether to publish a new version.

Do not create tags or bump the version by hand. The workflow owns both.

The first release is `v0.1.0`, cut when the pull request that adds the Release workflow merges and its gate passes.

## Version rules

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/). Merge pull requests with **Squash and merge**. GitHub uses the pull request title as the commit on `main`, except for a single-commit pull request, where it uses that commit's message. Check the title in the merge dialog before confirming, because it is what the workflow reads.

| Commit | Release |
| --- | --- |
| `feat` | Minor (`0.1.0` to `0.2.0`) |
| `fix`, `perf` | Patch (`0.1.0` to `0.1.1`) |
| Breaking change (`feat!`, `fix!`, or a `BREAKING CHANGE:` footer) | Major, or minor while the project is `0.x` |
| `chore`, `docs`, `test`, `ci`, `style`, `refactor`, `build` | None |

The project is configured with `allow_zero_version = true` and `major_on_zero = false`. While the version is `0.x`, a breaking change bumps the minor version instead of jumping to `1.0.0`.

If a push to `main` contains only commits that cut no release, the workflow finishes without publishing anything.

## What the workflow does

The steps run in this order:

1. **Gate.** Lint, type check, tests, and the safety scan run first on Python 3.11, 3.12, and 3.13. If any of them fails, no release happens.
2. **Version and changelog.** python-semantic-release bumps `__version__` in `src/runpod_vllm/__init__.py`, which is the single version source, and writes `CHANGELOG.md`. It commits both as `chore(release): X.Y.Z`, tags `vX.Y.Z`, and pushes the commit and tag to `main`.
3. **Build.** The wheel and the source distribution are built from the tagged commit.
4. **GitHub Release.** A release is created for the tag with both files attached. Its notes are GitHub's auto-generated notes, not the `CHANGELOG.md` entry.
5. **PyPI.** The package is published to PyPI through trusted publishing in the `pypi` GitHub environment.

The GitHub Release is created before the PyPI step on purpose. If PyPI publishing fails, the release and its files still exist.

The release commit does not start another run: pushes made with `GITHUB_TOKEN` do not trigger workflows, and `chore` cuts no release.

The workflow releases only the commit its gate tested. If another pull request merges while a run is in progress, that run skips the release and the newer run publishes both changes in one version.

`CHANGELOG.md` is generated. It does not exist until the first release, and it should not be edited by hand.

## Credentials

The workflow pushes the release commit and tag with the default `GITHUB_TOKEN`. PyPI publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), which authenticates with a short-lived OIDC token from GitHub Actions. No deploy key or API token is stored in the repository.

Branch protection on `main` that blocks direct pushes will break the release step.

## One-time PyPI setup

The project `runpod-vllm-deployer` is not on PyPI yet. Before the first publish can succeed, the owner must register a pending trusted publisher at <https://pypi.org/manage/account/publishing/> with these values:

| Field | Value |
| --- | --- |
| PyPI project name | `runpod-vllm-deployer` |
| Owner | `1solomonwakhungu` |
| Repository name | `runpod-vllm-deployer` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

Until this is done, the PyPI step fails on every release and the workflow run shows as failed. The tag and the GitHub Release are still created. After registering the publisher, publish the versions that were skipped with the manual run described below.

Once the first publish succeeds, PyPI creates the project and the publisher settings move to <https://pypi.org/manage/project/runpod-vllm-deployer/settings/publishing/>.

## Publish an existing version

Use this when a version was tagged but its PyPI publish failed, or when the GitHub Release is missing.

1. Open the Release workflow on the repository's Actions tab.
2. Select **Run workflow** and enter the existing version without the `v` prefix, for example `0.1.0`.

The run checks that the version matches the tag. If the GitHub Release exists, it downloads the attached wheel and source distribution and leaves the release as it is. If the release is missing, it builds both files and creates it. It then publishes the files to PyPI, skipping any that are already there. It never creates a new version, and it does not run the gate.

Use this run, not **Re-run failed jobs**, after a failed PyPI step. A rerun of the original run finds the release commit already on `main` and skips publishing.

## Rollback

PyPI does not allow a version to be uploaded twice, so a broken release is replaced, not rewritten.

1. Yank the version at <https://pypi.org/manage/project/runpod-vllm-deployer/releases/>. Yanking stops new installs from selecting it and keeps existing pins working.
2. Edit the GitHub Release for the broken version and note that it is superseded. Its files stay downloadable.
3. Merge the fix with a `fix:` commit.
4. The workflow publishes the next patch version.

Do not delete or move the tag, and do not remove the release commit from `main`.

## Checks

CI was removed from this repository in July 2026 (commit `8bffdb3`). The Release workflow is the only workflow, and its gate is the only automated check. It runs after a merge, not on pull requests, so contributors and reviewers still run `make check` locally before merging.

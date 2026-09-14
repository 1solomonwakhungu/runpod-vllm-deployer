from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATHS = (
    ROOT / "skills/runpod-vllm-gpu-deploy/SKILL.md",
    ROOT / ".claude/skills/runpod-vllm-gpu-deploy/SKILL.md",
)
EXPECTED_OPTIONS = {
    "plan": {
        "--model",
        "--name",
        "--gpu",
        "--gpu-count",
        "--tensor-parallel-size",
        "--container-disk-gb",
        "--volume-gb",
        "--min-vcpu-per-gpu",
        "--min-ram-per-gpu",
        "--max-model-len",
        "--gpu-memory-utilization",
        "--dtype",
        "--quantization",
        "--kv-cache-dtype",
        "--revision",
        "--trust-remote-code",
        "--reasoning-parser",
        "--image",
        "--cloud-type",
        "--data-center",
        "--port",
        "--env",
        "--help",
    },
    "deploy": {
        "--model",
        "--name",
        "--gpu",
        "--gpu-count",
        "--tensor-parallel-size",
        "--container-disk-gb",
        "--volume-gb",
        "--min-vcpu-per-gpu",
        "--min-ram-per-gpu",
        "--max-model-len",
        "--gpu-memory-utilization",
        "--dtype",
        "--quantization",
        "--kv-cache-dtype",
        "--revision",
        "--trust-remote-code",
        "--reasoning-parser",
        "--image",
        "--cloud-type",
        "--data-center",
        "--port",
        "--env",
        "--yes",
        "--help",
    },
    "list": {"--help"},
    "status": {"--help"},
    "wait": {"--base-url", "--timeout", "--interval", "--help"},
    "smoke-test": {
        "--base-url",
        "--model",
        "--bearer-token-env",
        "--timeout",
        "--help",
    },
    "destroy": {
        "--pod-id",
        "--yes",
        "--verify-timeout",
        "--verify-interval",
        "--help",
    },
}


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    assert content.startswith("---\n"), "frontmatter must start at byte 0"
    frontmatter, separator, body = content[4:].partition("\n---\n")
    assert separator, "frontmatter must have a closing delimiter"
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = re.fullmatch(r"(name|description): ([^\n]+)", line)
        assert match, f"invalid frontmatter line: {line!r}"
        key, value = match.groups()
        assert key not in metadata, f"duplicate frontmatter key: {key}"
        metadata[key] = value
    assert set(metadata) == {"name", "description"}
    return metadata, body


@pytest.mark.parametrize("path", SKILL_PATHS)
def test_skill_presence_frontmatter_and_body(path: Path) -> None:
    raw = path.read_bytes()
    assert raw.startswith(b"---\n")
    assert 0 < len(raw) < 100_000
    content = raw.decode("utf-8")
    metadata, body = parse_frontmatter(content)
    assert metadata["name"] == "runpod-vllm-gpu-deploy"
    assert 0 < len(metadata["description"]) < 1024
    assert "Use when" in metadata["description"]
    assert "Do not use" in metadata["description"]
    assert body.strip()


def test_skill_files_are_identical() -> None:
    assert SKILL_PATHS[0].read_bytes() == SKILL_PATHS[1].read_bytes()


@pytest.mark.parametrize("path", SKILL_PATHS)
def test_skill_has_no_private_or_unsafe_markers(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    forbidden_literals = (
        chr(0x2014),
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "Hermes" + "/scripts",
        ".env" + ".runpod",
        "TEST_" + "RESULTS.md",
        "Venture" + "Forgre",
    )
    assert not any(marker in content for marker in forbidden_literals)
    assert not re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", content, re.I)
    assert not re.search(r"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9]", content)
    assert not re.search(
        r"(?m)^\s*(?:export\s+)?(?:RUNPOD_API_KEY|HF_TOKEN|VLLM_API_KEY)\s*=\s*\S+",
        content,
    )


def test_documented_commands_match_live_help() -> None:
    content = SKILL_PATHS[0].read_text(encoding="utf-8")
    for command, expected_options in EXPECTED_OPTIONS.items():
        result = subprocess.run(
            [sys.executable, "-m", "runpod_vllm", command, "--help"],
            cwd=ROOT,
            env={**os.environ, "COLUMNS": "240", "NO_COLOR": "1"},
            check=True,
            capture_output=True,
            text=True,
        )
        actual_options = set(re.findall(r"--[a-z][a-z0-9-]*", result.stdout))
        assert actual_options == expected_options
        assert f"`runpod-vllm {command}" in content
        assert expected_options <= set(re.findall(r"--[a-z][a-z0-9-]*", content))


def test_repository_has_no_github_workflows() -> None:
    workflow_dir = ROOT / ".github/workflows"
    assert not workflow_dir.exists() or not any(workflow_dir.iterdir())


def test_readme_keeps_removed_content_absent() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "actions/workflows" not in readme
    assert "[![CI]" not in readme
    assert "[![Security checks]" not in readme
    assert "> Safety promise:" not in readme

#!/usr/bin/env python3
"""Fail when tracked repository text contains high-risk public-repo markers."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

LITERAL_MARKERS = (
    "\u2014",
    "/Users/",
    "Hermes/scripts",
    ".env.runpod",
    "TEST_RESULTS.md",
    "VentureForgre",
)

SECRET_PATTERNS = (
    re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"(?m)^\s*(?:export\s+)?(?:RUNPOD_API_KEY|HF_TOKEN|VLLM_API_KEY)\s*=\s*"
        r"(?!replace_with_|placeholder|example|<)[^\s#]+"
    ),
    re.compile(r"(?i)Authorization\s*:\s*Bearer\s+(?!<redacted>|\{)[A-Za-z0-9._~+\-/=]{12,}"),
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if path.resolve() == SELF or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT)
        for marker in LITERAL_MARKERS:
            if marker in text:
                findings.append(f"{relative}: contains prohibited marker {marker!r}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{relative}: matches credential pattern {pattern.pattern!r}")
    if findings:
        print("Safety scan failed:", file=sys.stderr)
        print("\n".join(f"- {finding}" for finding in findings), file=sys.stderr)
        return 1
    print(f"Safety scan passed for {len(tracked_files())} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

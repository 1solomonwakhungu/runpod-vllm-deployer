"""Atomic local teardown-state persistence."""

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from runpod_vllm.errors import StateError
from runpod_vllm.models import DeploymentState


def save_state(path: Path, state: DeploymentState) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state.to_dict(), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            with suppress(OSError):
                path.chmod(0o600)
        finally:
            if temporary.exists():
                temporary.unlink()
    except OSError as exc:
        raise StateError(f"Could not save teardown state at {path}: {exc}") from exc


def load_state(path: Path) -> DeploymentState:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("state root is not an object")
        return DeploymentState.from_dict(raw)
    except FileNotFoundError as exc:
        raise StateError(f"No deployment state found at {path}.") from exc
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StateError(f"Invalid deployment state at {path}: {exc}") from exc


def remove_state(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise StateError(f"Could not remove deployment state at {path}: {exc}") from exc

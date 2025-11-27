"""Watch-mode helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

from .discovery import _module_name_from_path


def snapshot_watchable_files(root: Path) -> dict[Path, float]:
    """Return map of watchable files to mtimes."""
    snapshot: dict[Path, float] = {}
    patterns = ("*.py", "*.pyjest")
    for pattern in patterns:
        for path in root.rglob(pattern):
            if any(part.startswith(".") for part in path.parts):
                continue
            try:
                snapshot[path] = path.stat().st_mtime
            except OSError:
                continue
    return snapshot


def detect_changes(previous: dict[Path, float], root: Path) -> tuple[set[Path], dict[Path, float]]:
    current = snapshot_watchable_files(root)
    changed: set[Path] = set()
    for path, mtime in current.items():
        if previous.get(path) != mtime:
            changed.add(path)
    for path in previous:
        if path not in current:
            changed.add(path)
    return changed, current


def targets_from_changed(changed: set[Path], default_targets: Sequence[str]) -> list[str]:
    """Derive targets to run from changed files."""
    if not changed:
        return list(default_targets)
    targets: list[str] = []
    for path in sorted(changed):
        if path.suffix == ".pyjest":
            targets.append(str(path))
        elif path.suffix == ".py":
            targets.append(_module_name_from_path(path))
    return targets or list(default_targets)


def wait_for_change(snapshot: dict[Path, float], root: Path, interval: float) -> tuple[set[Path], dict[Path, float]]:
    while True:
        changed, snapshot = detect_changes(snapshot, root)
        if changed:
            return changed, snapshot
        time.sleep(interval)

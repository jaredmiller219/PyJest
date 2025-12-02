"""Watch-mode helpers."""

from __future__ import annotations

import time
import threading
from pathlib import Path
from typing import Iterable, Sequence

from .discovery import _module_name_from_path

try:  # Optional fast backends
    from watchfiles import watch as watchfiles_watch  # type: ignore

    HAS_WATCHFILES = True
except Exception:
    HAS_WATCHFILES = False

try:
    from watchdog.events import FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer  # type: ignore

    HAS_WATCHDOG = True
except Exception:
    HAS_WATCHDOG = False


def snapshot_watchable_files(root: Path) -> dict[Path, float]:
    """Return map of watchable files to mtimes."""
    snapshot: dict[Path, float] = {}
    for path in _iter_watchable(root):
        mtime = _safe_mtime(path)
        if mtime is not None:
            snapshot[path] = mtime
    return snapshot


def detect_changes(previous: dict[Path, float], root: Path) -> tuple[set[Path], dict[Path, float]]:
    current = snapshot_watchable_files(root)
    changed = _diff_snapshots(previous, current)
    return changed, current


def has_fast_watcher() -> bool:
    return HAS_WATCHFILES or HAS_WATCHDOG


def next_change(snapshot: dict[Path, float], root: Path, interval: float) -> tuple[set[Path], dict[Path, float]]:
    if HAS_WATCHFILES:
        changed = _watchfiles_wait(root)
        return changed, snapshot_watchable_files(root)
    if HAS_WATCHDOG:
        changed = _watchdog_wait(root, interval)
        return changed, snapshot_watchable_files(root)
    return detect_changes(snapshot, root)


def targets_from_changed(changed: set[Path], default_targets: Sequence[str]) -> list[str]:
    """Derive targets to run from changed files."""
    if not changed:
        return list(default_targets)
    targets: list[str] = []
    for path in sorted(changed):
        if path.suffix in {".pyjest", ".pyj"}:
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


def _iter_watchable(root: Path) -> Iterable[Path]:
    patterns = (".py", ".pyj", ".pyjest")
    for path in root.rglob("*"):
        if path.is_dir() or _is_hidden(path):
            continue
        if path.suffix in patterns:
            yield path


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _safe_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _diff_snapshots(previous: dict[Path, float], current: dict[Path, float]) -> set[Path]:
    changed: set[Path] = set()
    for path, mtime in current.items():
        if previous.get(path) != mtime:
            changed.add(path)
    for path in previous:
        if path not in current:
            changed.add(path)
    return changed


def _watchfiles_wait(root: Path) -> set[Path]:
    for changes in watchfiles_watch(str(root), recursive=True):
        if not changes:
            continue
        paths = {Path(change[1]) for change in changes}
        return paths
    return set()


def _watchdog_wait(root: Path, timeout: float) -> set[Path]:
    fired = threading.Event()
    changed: set[Path] = set()

    class Handler(FileSystemEventHandler):  # type: ignore[misc]
        def on_any_event(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            changed.add(Path(event.src_path))
            fired.set()

    observer = Observer()
    handler = Handler()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()
    try:
        fired.wait(timeout=timeout or 1.0)
    finally:
        observer.stop()
        observer.join()
    return changed

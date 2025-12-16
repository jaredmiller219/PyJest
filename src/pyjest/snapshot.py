"""Minimal snapshot storage and assertion support."""

from __future__ import annotations

import inspect
import json
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .discovery import PROJECT_ROOT


def _caller_test_context() -> tuple[str, str]:
    """Best-effort guess of (module, test_name) from the stack."""
    for frame_info in inspect.stack():
        frame = frame_info.frame
        self_obj = frame.f_locals.get("self")
        method_name = frame.f_code.co_name
        module_name = frame.f_globals.get("__name__", "unknown")
        if hasattr(self_obj, "__class__") and module_name != __name__:
            # Heuristic: inside a unittest.TestCase method
            return module_name, f"{self_obj.__class__.__name__}::{method_name}"
    return "unknown", "unknown"


def _default_snapshot_name(module_name: str, test_name: str) -> str:
    return f"{module_name}::{test_name}"


def _snapshot_file_for_module(root: Path, module_name: str) -> Path:
    rel = module_name.replace(".", "/")
    return root / "__snapshots__" / f"{rel}.snap.json"


@dataclass
class SnapshotStore:
    root: Path = field(default_factory=lambda: PROJECT_ROOT)
    update: bool = False
    show_summary: bool = False
    _cache: Dict[Path, Dict[str, Any]] = field(default_factory=dict)
    _touched: list[tuple[Path, str, str]] = field(default_factory=list)

    def configure(self, root: Path, update: bool, show_summary: bool = False) -> None:
        self.root = root
        self.update = update
        self.show_summary = show_summary
        self._cache.clear()
        self._touched.clear()

    def _load_file(self, path: Path) -> Dict[str, Any]:
        if path in self._cache:
            return self._cache[path]
        content = self._read_snapshot_file(path)
        self._cache[path] = content
        return content

    def _save_file(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True))
        self._cache[path] = data

    def assert_match(self, value: Any, name: Optional[str] = None) -> None:
        module_name, test_name = _caller_test_context()
        snap_name = name or _default_snapshot_name(module_name, test_name)
        file_path = _snapshot_file_for_module(self.root, module_name)
        snapshots = self._load_file(file_path)
        if snap_name not in snapshots:
            self._handle_missing_snapshot(snap_name, snapshots, file_path, value)
            return
        self._compare_or_update_snapshot(snap_name, snapshots, file_path, value)

    def _handle_missing_snapshot(self, snap_name: str, snapshots: Dict[str, Any], file_path: Path, value: Any) -> None:
        if not self.update:
            raise AssertionError(
                f"Snapshot '{snap_name}' not found. Re-run with --updateSnapshot to create it."
            )
        snapshots[snap_name] = value
        self._save_file(file_path, snapshots)
        self._note_touched(file_path, snap_name, "created")
        if self.show_summary:
            print(f"[snapshot] created {file_path}:{snap_name}")

    def _compare_or_update_snapshot(
        self, snap_name: str, snapshots: Dict[str, Any], file_path: Path, value: Any
    ) -> None:
        expected = snapshots[snap_name]
        if expected == value:
            return
        if self.update:
            snapshots[snap_name] = value
            self._save_file(file_path, snapshots)
            self._note_touched(file_path, snap_name, "updated")
            if self.show_summary:
                print(f"[snapshot] updated {file_path}:{snap_name}")
            return
        diff = _render_diff(expected, value)
        raise AssertionError(
            f"Snapshot mismatch for '{snap_name}'. "
            "Re-run with --updateSnapshot to accept new output.\n"
            f"Expected: {expected!r}\nReceived: {value!r}\nDiff:\n{diff}"
        )

    def _read_snapshot_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            content = json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
        if not isinstance(content, dict):
            return {}
        return content

    def _note_touched(self, file_path: Path, snap_name: str, action: str) -> None:
        self._touched.append((file_path, snap_name, action))

    def summary_lines(self) -> list[str]:
        if not self._touched:
            return []
        lines = ["Snapshots touched:"]
        for file_path, snap_name, action in self._touched:
            lines.append(f"  - {action}: {file_path}:{snap_name}")
        return lines

    def clean_orphans(self) -> list[Path]:
        """Delete snapshot files whose corresponding modules no longer exist."""
        removed: list[Path] = []
        base = self.root / "__snapshots__"
        if not base.exists():
            return removed
        for path in base.rglob("*.snap.json"):
            module_rel = path.relative_to(base).with_suffix(".py")
            module_path = self.root / module_rel
            if not module_path.exists():
                try:
                    path.unlink()
                    removed.append(path)
                except Exception:
                    continue
        return removed


STORE = SnapshotStore()


def print_snapshot_summary() -> None:
    if not STORE.show_summary:
        return
    lines = STORE.summary_lines()
    if not lines:
        print("Snapshots touched: none")
        return
    for line in lines:
        print(line)


def _render_diff(expected: Any, actual: Any) -> str:
    left = json.dumps(expected, indent=2, sort_keys=True)
    right = json.dumps(actual, indent=2, sort_keys=True)
    diff = difflib.unified_diff(
        left.splitlines(),
        right.splitlines(),
        fromfile="expected",
        tofile="received",
        lineterm="",
    )
    lines = list(diff)
    if not lines:
        return ""
    max_lines = 200
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines truncated)"])
    return "\n".join(lines)

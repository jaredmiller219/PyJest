"""Minimal snapshot storage and assertion support."""

from __future__ import annotations

import inspect
import json
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
    _cache: Dict[Path, Dict[str, Any]] = field(default_factory=dict)

    def configure(self, root: Path, update: bool) -> None:
        self.root = root
        self.update = update
        self._cache.clear()

    def _load_file(self, path: Path) -> Dict[str, Any]:
        if path in self._cache:
            return self._cache[path]
        if not path.exists():
            data: Dict[str, Any] = {}
            self._cache[path] = data
            return data
        try:
            content = json.loads(path.read_text())
        except json.JSONDecodeError:
            content = {}
        if not isinstance(content, dict):
            content = {}
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
            if not self.update:
                raise AssertionError(
                    f"Snapshot '{snap_name}' not found. Re-run with --updateSnapshot to create it."
                )
            snapshots[snap_name] = value
            self._save_file(file_path, snapshots)
            return
        expected = snapshots[snap_name]
        if expected != value:
            if self.update:
                snapshots[snap_name] = value
                self._save_file(file_path, snapshots)
                return
            raise AssertionError(
                f"Snapshot mismatch for '{snap_name}'. "
                "Re-run with --updateSnapshot to accept new output.\n"
                f"Expected: {expected!r}\nReceived: {value!r}"
            )


STORE = SnapshotStore()

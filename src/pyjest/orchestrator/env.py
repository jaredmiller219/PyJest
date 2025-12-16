"""Environment preparation for running tests."""

from __future__ import annotations

import os
from pathlib import Path

from ..discovery import _ensure_python_project, _set_project_root
from ..assertions import configure_diffs
from ..snapshot import STORE as SNAPSHOTS


def prepare_environment(args) -> None:
    requested_root = args.root
    root = (requested_root or Path.cwd()).expanduser().resolve()
    if requested_root:
        if not root.exists():
            raise SystemExit(f"--root path not found: {root}")
        if not root.is_dir():
            raise SystemExit(f"--root must be a directory: {root}")
        os.chdir(root)
    args.root = root
    _set_project_root(root)
    SNAPSHOTS.configure(root=root, update=args.updateSnapshot, show_summary=args.snapshot_summary)
    if getattr(args, "snapshot_clean", False):
        removed = SNAPSHOTS.clean_orphans()
        if removed:
            print(f"Removed {len(removed)} orphaned snapshot file(s).")
    configure_diffs(args.max_diff_lines, args.color_diffs)
    _ensure_python_project(root)

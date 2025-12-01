"""Environment preparation for running tests."""

from __future__ import annotations

import os
from pathlib import Path

from ..discovery import _ensure_python_project, _set_project_root
from ..assertions import configure_diffs
from ..snapshot import STORE as SNAPSHOTS


def prepare_environment(args) -> None:
    root = (args.root or Path.cwd()).expanduser().resolve()
    if args.root:
        os.chdir(root)
    args.root = root
    _set_project_root(root)
    SNAPSHOTS.configure(root=root, update=args.updateSnapshot, show_summary=args.snapshot_summary)
    configure_diffs(args.max_diff_lines, args.color_diffs)
    _ensure_python_project(root)

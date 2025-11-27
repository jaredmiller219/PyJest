"""PyJest CLI orchestration."""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from typing import Sequence

from .assertions import expect, expect_async
from .cli import parse_args
from .coverage_support import coverage_threshold_failed, make_coverage, report_coverage
from .discovery import (
    _ensure_python_project,
    _load_targets,
    _set_project_root,
    mark_pyjest,
    marked_modules,
)
from .reporter import JestStyleTestRunner
from .watch import detect_changes, snapshot_watchable_files, targets_from_changed

__all__ = ["expect", "expect_async", "mark_pyjest", "marked_modules", "main"]


def _run_suite(loader: unittest.TestLoader, runner: JestStyleTestRunner, args, targets: Sequence[str]):
    cov = make_coverage(args.root) if args.coverage else None
    if cov:
        cov.start()
    suite = _load_targets(loader, targets, args.pattern)
    result = runner.run(suite)
    coverage_percent: float | None = None
    if cov:
        cov.stop()
        cov.save()
        coverage_percent = report_coverage(cov, args.coverage_html)
    return result, coverage_percent


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    args.failfast = args.failfast or args.bail
    if args.maxWorkers != 1:
        raise SystemExit("Parallel workers not yet supported. Use --maxWorkers 1 or omit it.")
    if args.coverage_html is not None or args.coverage_threshold is not None:
        args.coverage = True
    root = (args.root or Path.cwd()).expanduser().resolve()
    if args.root:
        os.chdir(root)
    args.root = root
    _set_project_root(root)
    _ensure_python_project(root)
    loader = unittest.TestLoader()
    runner = JestStyleTestRunner(failfast=args.failfast, buffer=args.buffer, stream=sys.stdout)

    if not args.watch:
        result, coverage_percent = _run_suite(loader, runner, args, args.targets)
        exit_fail = not result.wasSuccessful()
        if coverage_threshold_failed(coverage_percent, args.coverage_threshold):
            exit_fail = True
        return 0 if not exit_fail else 1

    snapshot = snapshot_watchable_files(root)
    targets = args.targets
    last_fail = False
    try:
        while True:
            result, coverage_percent = _run_suite(loader, runner, args, targets)
            last_fail = not result.wasSuccessful() or coverage_threshold_failed(
                coverage_percent, args.coverage_threshold
            )
            changed, snapshot = detect_changes(snapshot, root)
            while not changed:
                time.sleep(args.watch_interval)
                changed, snapshot = detect_changes(snapshot, root)
            display = ", ".join(str(path.relative_to(root)) for path in sorted(changed)) if changed else "unknown"
            print(f"\nChange detected: {display}")
            targets = targets_from_changed(changed, args.targets) if args.onlyChanged else args.targets
    except KeyboardInterrupt:
        print("\nWatch mode interrupted. Exiting.")
        return 0 if not last_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())

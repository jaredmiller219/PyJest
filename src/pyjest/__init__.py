"""PyJest CLI orchestration."""

from __future__ import annotations

import io
import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, Sequence

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
from .snapshot import STORE as SNAPSHOTS
from .watch import detect_changes, snapshot_watchable_files, targets_from_changed

__all__ = ["expect", "expect_async", "mark_pyjest", "marked_modules", "main"]


def _run_suite(
    loader: unittest.TestLoader, args, targets: Sequence[str], stream=None
) -> tuple[unittest.result.TestResult, float | None, str]:
    cov = make_coverage(args.root) if args.coverage else None
    if cov:
        cov.start()
    if stream is None:
        stream = sys.stdout
    suite = _load_targets(loader, targets, args.pattern)
    runner = JestStyleTestRunner(failfast=args.failfast, buffer=args.buffer, stream=stream)
    result = runner.run(suite)
    coverage_percent: float | None = None
    if cov:
        cov.stop()
        cov.save()
        coverage_percent = report_coverage(cov, args.coverage_html)
    output_text = stream.getvalue() if isinstance(stream, io.StringIO) else ""
    return result, coverage_percent, output_text


def _failed_modules(result: unittest.result.TestResult) -> list[str]:
    modules: set[str] = set()
    failing_tests: Iterable[unittest.case.TestCase] = [test for test, _ in result.failures + result.errors]  # type: ignore[operator]
    for test in failing_tests:
        modules.add(test.__class__.__module__)
    return sorted(modules)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    args.failfast = args.failfast or args.bail
    if args.maxWorkers < 1:
        raise SystemExit("--maxWorkers must be >= 1")
    if args.coverage_html is not None or args.coverage_threshold is not None:
        args.coverage = True
    root = (args.root or Path.cwd()).expanduser().resolve()
    if args.root:
        os.chdir(root)
    args.root = root
    _set_project_root(root)
    SNAPSHOTS.configure(root=root, update=args.updateSnapshot)
    _ensure_python_project(root)
    loader = unittest.TestLoader()
    if not args.watch:
        if args.maxWorkers > 1 and len(args.targets) > 1:
            exit_fail = False
            outputs: list[str] = []
            with ThreadPoolExecutor(max_workers=args.maxWorkers) as pool:
                futures = [
                    pool.submit(
                        _run_suite,
                        unittest.TestLoader(),
                        args,
                        [target],
                        io.StringIO(),
                    )
                    for target in args.targets
                ]
                for future in futures:
                    result, coverage_percent, text = future.result()
                    outputs.append(text)
                    if coverage_threshold_failed(coverage_percent, args.coverage_threshold) or not result.wasSuccessful():
                        exit_fail = True
            for text in outputs:
                if text:
                    sys.stdout.write(text)
            return 0 if not exit_fail else 1
        result, coverage_percent, _ = _run_suite(loader, args, args.targets)
        exit_fail = not result.wasSuccessful()
        if coverage_threshold_failed(coverage_percent, args.coverage_threshold):
            exit_fail = True
        return 0 if not exit_fail else 1

    snapshot = snapshot_watchable_files(root)
    targets = args.targets
    last_fail = False
    failed_targets: list[str] = []
    try:
        while True:
            result, coverage_percent, _ = _run_suite(loader, args, targets)
            last_fail = not result.wasSuccessful() or coverage_threshold_failed(
                coverage_percent, args.coverage_threshold
            )
            failed_targets = _failed_modules(result)
            changed, snapshot = detect_changes(snapshot, root)
            while not changed:
                time.sleep(args.watch_interval)
                changed, snapshot = detect_changes(snapshot, root)
            if args.watch_debounce:
                time.sleep(args.watch_debounce)
                changed2, snapshot = detect_changes(snapshot, root)
                changed |= changed2
            display = ", ".join(str(path.relative_to(root)) for path in sorted(changed)) if changed else "unknown"
            print(f"\nChange detected: {display}")
            if args.onlyChanged:
                targets = targets_from_changed(changed, args.targets)
            elif failed_targets:
                targets = failed_targets
            else:
                targets = args.targets
    except KeyboardInterrupt:
        print("\nWatch mode interrupted. Exiting.")
        return 0 if not last_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())

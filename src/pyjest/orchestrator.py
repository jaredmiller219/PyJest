"""Core orchestration for running and watching tests."""

from __future__ import annotations

import io
import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, Sequence

from .change_map import infer_targets_from_changes
from .coverage_support import coverage_threshold_failed, make_coverage, report_coverage
from .discovery import _ensure_python_project, _load_targets, _set_project_root
from .reporter import JestStyleTestRunner
from .snapshot import STORE as SNAPSHOTS
from .watch import detect_changes, snapshot_watchable_files, targets_from_changed


def run_suite(
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


def failed_modules(result: unittest.result.TestResult) -> list[str]:
    modules: set[str] = set()
    failing_tests: Iterable[unittest.case.TestCase] = [
        test for test, _ in result.failures + result.errors  # type: ignore[operator]
    ]
    for test in failing_tests:
        modules.add(test.__class__.__module__)
    return sorted(modules)


def _run_parallel_targets(args) -> int:
    exit_fail = False
    outputs: list[str] = []
    with ThreadPoolExecutor(max_workers=args.maxWorkers) as pool:
        futures = [
            pool.submit(
                run_suite,
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


def _run_serial_targets(args, targets: Sequence[str]) -> int:
    loader = unittest.TestLoader()
    result, coverage_percent, _ = run_suite(loader, args, targets)
    exit_fail = not result.wasSuccessful()
    if coverage_threshold_failed(coverage_percent, args.coverage_threshold):
        exit_fail = True
    return 0 if not exit_fail else 1


def _wait_for_change(
    snapshot: dict[Path, float], root: Path, interval: float, debounce: float
) -> tuple[set[Path], dict[Path, float]]:
    changed: set[Path] = set()
    while not changed:
        changed, snapshot = detect_changes(snapshot, root)
        if changed:
            break
        time.sleep(interval)
    if debounce:
        time.sleep(debounce)
        extra, snapshot = detect_changes(snapshot, root)
        changed |= extra
    return changed, snapshot


def _print_change_notice(changed: set[Path], root: Path) -> None:
    display = ", ".join(str(path.relative_to(root)) for path in sorted(changed)) if changed else "unknown"
    print(f"\nChange detected: {display}")


def _next_targets(args, changed: set[Path], failed_targets: Sequence[str]) -> list[str]:
    if args.onlyChanged:
        return targets_from_changed(changed, args.targets)
    if args.run_failures_first and failed_targets:
        return list(failed_targets)
    return infer_targets_from_changes(changed, args.targets)


def run_once(args) -> int:
    if args.maxWorkers > 1 and len(args.targets) > 1:
        return _run_parallel_targets(args)
    return _run_serial_targets(args, args.targets)


def run_watch(args) -> int:
    root = args.root
    loader = unittest.TestLoader()
    snapshot = snapshot_watchable_files(root)
    targets = args.targets
    last_fail = False
    failed_targets: list[str] = []
    try:
        while True:
            result, coverage_percent, _ = run_suite(loader, args, targets)
            last_fail = not result.wasSuccessful() or coverage_threshold_failed(
                coverage_percent, args.coverage_threshold
            )
            failed_targets = failed_modules(result)
            changed, snapshot = _wait_for_change(snapshot, root, args.watch_interval, args.watch_debounce)
            _print_change_notice(changed, root)
            targets = _next_targets(args, changed, failed_targets)
    except KeyboardInterrupt:
        print("\nWatch mode interrupted. Exiting.")
        return 0 if not last_fail else 1


def prepare_environment(args) -> None:
    root = (args.root or Path.cwd()).expanduser().resolve()
    if args.root:
        os.chdir(root)
    args.root = root
    _set_project_root(root)
    SNAPSHOTS.configure(root=root, update=args.updateSnapshot)
    _ensure_python_project(root)

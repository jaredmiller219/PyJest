"""Single-run orchestration."""

from __future__ import annotations

import sys
import os
import json
import io
import fnmatch
import unittest
from pathlib import Path
from copy import copy
from typing import Sequence

from ..coverage_support import coverage_threshold_failed
from .runner import collect_parallel_results, run_suite, sequential_result, failing_test_ids

LAST_FAILED_FILE = ".pyjest_lastfail"

def run_once(args) -> int:
    _maybe_apply_last_failed(args)
    try:
        if args.maxWorkers > 1 and len(args.targets) > 1:
            return _run_parallel_targets(args)
        return _run_serial_targets(args, args.targets)
    except KeyboardInterrupt:
        return 130


def _run_parallel_targets(args) -> int:
    targets = _chunk_targets(args.targets, args.maxTargetsPerWorker)
    args_targets_backup = args.targets
    args.targets = targets
    results, outputs = collect_parallel_results(args)
    args.targets = args_targets_backup
    all_failing_ids: list[str] = []
    for res in results:
        all_failing_ids.extend(failing_test_ids(res))
    _persist_last_failed(args.root, all_failing_ids)
    exit_fail = any(not res.wasSuccessful() for res in results)
    _flush_outputs(outputs)
    return 0 if not exit_fail else 1


def _run_serial_targets(args, targets: Sequence[str]) -> int:
    result, coverage_percent = sequential_result(args, targets)
    if getattr(args, "rerun", 0) and not result.wasSuccessful():
        result = _rerun_failures(args, result)
    _persist_last_failed(args.root, failing_test_ids(result))
    exit_fail = not result.wasSuccessful()
    if coverage_threshold_failed(coverage_percent, args.coverage_threshold):
        exit_fail = True
    if _modules_below_threshold(result, getattr(args, "coverage_threshold_module", {}), args.root):
        exit_fail = True
    return 0 if not exit_fail else 1


def _flush_outputs(outputs: Sequence[str]) -> None:
    for text in outputs:
        if text:
            sys.stdout.write(text)


def _chunk_targets(targets: Sequence[str], max_per_worker: int) -> list[list[str]]:
    if max_per_worker and max_per_worker > 0:
        return [list(targets[i : i + max_per_worker]) for i in range(0, len(targets), max_per_worker)]
    return [[target] for target in targets]


def _maybe_apply_last_failed(args) -> None:
    if not getattr(args, "last_failed", False):
        return
    path = args.root / LAST_FAILED_FILE
    if not path.exists():
        return
    try:
        ids = json.loads(path.read_text())
    except Exception:
        return
    if ids:
        args.targets = ids


def _persist_last_failed(root, failing_ids: Sequence[str]) -> None:
    path = root / LAST_FAILED_FILE
    try:
        path.write_text(json.dumps(list(failing_ids)))
    except Exception:
        return


def _rerun_failures(args, initial_result):
    failing_ids = failing_test_ids(initial_result)
    attempts = getattr(args, "rerun", 0)
    if not failing_ids or attempts <= 0:
        return initial_result
    rerun_args = copy(args)
    rerun_args.coverage = False
    rerun_args.coverage_html = None
    rerun_args.coverage_threshold = None
    rerun_args.coverage_threshold_module = {}
    rerun_args.coverage_json = None
    rerun_args.report_format = ["console"]
    for _ in range(attempts):
        rerun_result, _, _ = run_suite(
            unittest.TestLoader(),
            rerun_args,
            failing_ids,
            stream=io.StringIO(),
        )
        failing_ids = failing_test_ids(rerun_result)
        if not failing_ids:
            return rerun_result
    return rerun_result


def _modules_below_threshold(result, thresholds: dict[str, float], root: Path) -> bool:
    if not thresholds:
        return False
    stats = getattr(result, "_coverage_file_stats", None) or []
    failed = False
    for entry in stats:
        filename = entry.get("filename")
        percent = entry.get("percent", 0.0)
        if not filename:
            continue
        try:
            rel = Path(filename).resolve().relative_to(root)
        except Exception:
            rel = Path(filename)
        module = rel.with_suffix("").as_posix().replace("/", ".")
        for pattern, threshold in thresholds.items():
            if fnmatch.fnmatch(module, pattern) and percent < threshold:
                print(f"Coverage threshold not met for {module}: {percent:.2f}% < {threshold:.2f}%")
                failed = True
    return failed

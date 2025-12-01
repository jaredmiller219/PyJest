"""Single-run orchestration."""

from __future__ import annotations

import sys
from typing import Sequence

from ..coverage_support import coverage_threshold_failed
from .runner import collect_parallel_results, run_suite, sequential_result


def run_once(args) -> int:
    if args.maxWorkers > 1 and len(args.targets) > 1:
        return _run_parallel_targets(args)
    return _run_serial_targets(args, args.targets)


def _run_parallel_targets(args) -> int:
    targets = _chunk_targets(args.targets, args.maxTargetsPerWorker)
    args_targets_backup = args.targets
    args.targets = targets
    results, outputs = collect_parallel_results(args)
    args.targets = args_targets_backup
    exit_fail = any(not res.wasSuccessful() for res in results)
    _flush_outputs(outputs)
    return 0 if not exit_fail else 1


def _run_serial_targets(args, targets: Sequence[str]) -> int:
    result, coverage_percent = sequential_result(args, targets)
    exit_fail = not result.wasSuccessful()
    if coverage_threshold_failed(coverage_percent, args.coverage_threshold):
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

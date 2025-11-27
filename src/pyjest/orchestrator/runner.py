"""Shared runner and coverage helpers."""

from __future__ import annotations

import io
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

from ..coverage_support import coverage_threshold_failed, make_coverage, report_coverage
from ..discovery import _load_targets
from ..reporter import JestStyleTestRunner


def run_suite(
    loader: unittest.TestLoader, args, targets: Sequence[str], stream=None
) -> tuple[unittest.result.TestResult, float | None, str]:
    cov = _start_coverage_if_needed(args)
    stream = stream or sys.stdout
    suite = _load_targets(loader, targets, args.pattern)
    result = _run_suite_with_runner(suite, stream, args)
    coverage_percent = _finish_coverage(cov, args.coverage_html)
    output_text = stream.getvalue() if isinstance(stream, io.StringIO) else ""
    return result, coverage_percent, output_text


def failed_modules(result: unittest.result.TestResult) -> list[str]:
    modules: set[str] = set()
    failing_tests = [test for test, _ in result.failures + result.errors]  # type: ignore[operator]
    for test in failing_tests:
        modules.add(test.__class__.__module__)
    return sorted(modules)


def collect_parallel_results(args) -> tuple[list[unittest.result.TestResult], list[str]]:
    outputs: list[str] = []
    results: list[unittest.result.TestResult] = []
    with ThreadPoolExecutor(max_workers=args.maxWorkers) as pool:
        futures = [_submit_parallel_task(pool, args, target) for target in args.targets]
        for result, threshold_failed, text in _gather_results(futures, args.coverage_threshold):
            outputs.append(text)
            if threshold_failed:
                result.failures.append(("coverage", "threshold not met"))  # type: ignore[arg-type]
            results.append(result)
    return results, outputs


def sequential_result(args, targets: Sequence[str]) -> tuple[unittest.result.TestResult, float | None]:
    loader = unittest.TestLoader()
    result, coverage_percent, _ = run_suite(loader, args, targets)
    return result, coverage_percent


def record_watch_outcome(
    result: unittest.result.TestResult, coverage_percent: float | None, threshold: float | None
) -> tuple[bool, list[str]]:
    last_fail = not result.wasSuccessful() or coverage_threshold_failed(coverage_percent, threshold)
    return last_fail, failed_modules(result)


def _gather_results(futures, threshold: float | None):
    for future in futures:
        result, coverage_percent, text = future.result()
        threshold_failed = coverage_threshold_failed(coverage_percent, threshold)
        yield result, threshold_failed, text


def _start_coverage_if_needed(args):
    if not args.coverage:
        return None
    cov = make_coverage(args.root)
    cov.start()
    return cov


def _finish_coverage(cov, html_dir: str | None) -> float | None:
    if not cov:
        return None
    cov.stop()
    cov.save()
    return report_coverage(cov, html_dir)


def _run_suite_with_runner(suite: unittest.TestSuite, stream, args):
    runner = JestStyleTestRunner(failfast=args.failfast, buffer=args.buffer, stream=stream)
    return runner.run(suite)


def _submit_parallel_task(pool: ThreadPoolExecutor, args, target: str):
    return pool.submit(
        run_suite,
        unittest.TestLoader(),
        args,
        [target],
        io.StringIO(),
    )

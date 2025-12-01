"""Shared runner and coverage helpers."""

from __future__ import annotations

import io
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from typing import Sequence

from ..coverage_support import coverage_threshold_failed, make_coverage, report_coverage
from ..discovery import _load_targets, _format_test_title
from ..reporter import JestStyleTestRunner
from ..reporting import emit_reports


def run_suite(
    loader: unittest.TestLoader, args, targets: Sequence[str], stream=None
) -> tuple[unittest.result.TestResult, float | None, str]:
    cov = _start_coverage_if_needed(args)
    stream = stream or sys.stdout
    suite = _load_targets(loader, targets, args.pattern, args.pattern_exclude, args.ignore)
    start = time.perf_counter()
    result = _run_suite_with_runner(suite, stream, args)
    duration = time.perf_counter() - start
    coverage_percent = _finish_coverage(cov, args.coverage_html, args.coverage_bars)
    emit_reports(result, coverage_percent, duration, args)
    output_text = stream.getvalue() if isinstance(stream, io.StringIO) else ""
    label = getattr(args, "report_suffix", None)
    if label and output_text:
        output_text = _prefix_lines(output_text, f"[{label}] ")
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
        futures = [_submit_parallel_task(pool, args, target_group) for target_group in args.targets]
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
) -> tuple[bool, list[str], str | None]:
    last_fail = not result.wasSuccessful() or coverage_threshold_failed(coverage_percent, threshold)
    detail = None
    if result.failures or result.errors:
        test, err = (result.failures + result.errors)[0]  # type: ignore[operator]
        detail = f"{_format_test_title(test)}: {err.splitlines()[0] if err else ''}"
    return last_fail, failed_modules(result), detail


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


def _finish_coverage(cov, html_dir: str | None, show_bars: bool) -> float | None:
    if not cov:
        return None
    cov.stop()
    cov.save()
    return report_coverage(cov, html_dir, show_bars)


def _run_suite_with_runner(suite: unittest.TestSuite, stream, args):
    spinner = bool(args.buffer)
    runner = JestStyleTestRunner(
        failfast=args.failfast,
        buffer=args.buffer,
        stream=stream,
        spinner=spinner,
        report_modules=args.report_modules,
        report_suite_table=args.report_suite_table,
        report_outliers=args.report_outliers,
    )
    return runner.run(suite)


def _submit_parallel_task(pool: ThreadPoolExecutor, args, target: Sequence[str]):
    task_args = copy(args)
    label = ",".join(target)
    task_args.report_suffix = label
    return pool.submit(
        run_suite,
        unittest.TestLoader(),
        task_args,
        target,
        io.StringIO(),
    )


def _prefix_lines(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" if line.strip() else line for line in text.splitlines())

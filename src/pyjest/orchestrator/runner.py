"""Shared runner and coverage helpers."""

from __future__ import annotations

import io
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from typing import Sequence
import re
import fnmatch
from pathlib import Path

from ..coverage_support import coverage_threshold_failed, make_coverage, report_coverage
from ..discovery import _load_targets
from ..reporter import JestStyleTestRunner
from ..reporting import emit_reports


def run_suite(
    loader: unittest.TestLoader, args, targets: Sequence[str], stream=None
) -> tuple[unittest.result.TestResult, float | None, str]:
    cov = _start_coverage_if_needed(args)
    stream = stream or sys.stdout
    test_name_pattern = re.compile(args.testNamePattern) if getattr(args, "testNamePattern", None) else None
    suite = _load_targets(
        loader,
        targets,
        args.pattern,
        args.pattern_exclude,
        args.ignore,
        include_standard=not getattr(args, "pyjest_only", False),
        include_pyjest=True,
        test_name_pattern=test_name_pattern,
        module_pattern=getattr(args, "module_pattern", None),
        tags=getattr(args, "tag", ()),
    )
    start = time.perf_counter()
    result = _run_suite_with_runner(suite, stream, args)
    duration = time.perf_counter() - start
    coverage_percent, coverage_stats = _finish_coverage(cov, args.coverage_html, args.coverage_bars, getattr(args, "coverage_json", None))
    setattr(result, "_coverage_file_stats", coverage_stats)
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


def failing_test_ids(result: unittest.result.TestResult) -> list[str]:
    failing_tests = [test for test, _ in result.failures + result.errors]  # type: ignore[operator]
    return [test.id() for test in failing_tests]


def collect_parallel_results(args) -> tuple[list[unittest.result.TestResult], list[str]]:
    outputs: list[str] = []
    results: list[unittest.result.TestResult] = []
    pool = ThreadPoolExecutor(max_workers=args.maxWorkers)
    futures = [_submit_parallel_task(pool, args, target_group) for target_group in args.targets]
    try:
        for result, threshold_failed, text in _gather_results(
            futures, args.coverage_threshold, getattr(args, "coverage_threshold_module", {}), args.root
        ):
            outputs.append(text)
            if threshold_failed:
                result.failures.append(("coverage", "threshold not met"))  # type: ignore[arg-type]
            results.append(result)
    except KeyboardInterrupt:
        for future in futures:
            future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    except Exception:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
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
        method_name = getattr(test, "_testMethodName", "")
        fn = getattr(test, method_name, None)
        label = getattr(fn, "__pyjest_test__", None) if fn else None
        if not label:
            label = getattr(test, "__pyjest_test__", None) or ""
        detail = f"{label}: {err.splitlines()[0] if err else ''}"
    return last_fail, failed_modules(result), detail


def _gather_results(futures, threshold: float | None, module_thresholds: dict[str, float], root: Path):
    for future in futures:
        result, coverage_percent, text = future.result()
        threshold_failed = coverage_threshold_failed(coverage_percent, threshold) or _module_thresholds_failed(
            getattr(result, "_coverage_file_stats", None) or [], module_thresholds, root
        )
        yield result, threshold_failed, text


def _start_coverage_if_needed(args):
    if not args.coverage:
        return None
    cov = make_coverage(args.root)
    cov.start()
    return cov


def _finish_coverage(
    cov, html_dir: str | None, show_bars: bool, json_path: str | None
) -> tuple[float | None, list[dict] | None]:
    if not cov:
        return None, None
    cov.stop()
    cov.save()
    percent, stats = report_coverage(cov, html_dir, show_bars, json_path)
    setattr(cov, "_pyjest_file_stats", stats)
    return percent, stats


def _run_suite_with_runner(suite: unittest.TestSuite, stream, args):
    fancy_level = getattr(args, "progress_fancy", 0)
    spinner = fancy_level in (0, 1)  # default and one-line stats modes use spinner
    runner = JestStyleTestRunner(
        failfast=args.failfast,
        buffer=args.buffer,
        stream=stream,
        spinner=spinner,
        report_modules=args.report_modules,
        report_suite_table=args.report_suite_table,
        report_outliers=args.report_outliers,
        progress_fancy=fancy_level,
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


def _module_thresholds_failed(stats: list[dict], thresholds: dict[str, float], root: Path) -> bool:
    if not thresholds:
        return False
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
                failed = True
    return failed

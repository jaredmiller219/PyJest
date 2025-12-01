"""CLI argument parsing."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the test suite with Jest-style output."
    )
    _add_watch_args(parser)
    _add_target_args(parser)
    _add_execution_args(parser)
    _add_coverage_args(parser)
    _add_reporting_args(parser)
    _add_diff_args(parser)
    parser.add_argument("--buffer", "--buf", action="store_true", help="Buffer stdout/stderr during tests")
    return parser.parse_args(argv)


def _add_watch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--watch",
        "--w",
        action="store_true",
        help="Watch for filesystem changes and re-run tests",
    )
    parser.add_argument(
        "--watch-interval",
        "--wi",
        type=float,
        default=1.0,
        help="Polling interval in seconds when using --watch (default: %(default)s)",
    )
    parser.add_argument(
        "--watch-debounce",
        "--wd",
        type=float,
        default=0.2,
        help="Extra debounce delay after a change is detected (default: %(default)s)",
    )
    parser.add_argument(
        "--run-failures-first",
        "--rff",
        action="store_true",
        help="In watch mode, prioritize rerunning previously failing modules",
    )
    parser.add_argument(
        "--onlyChanged",
        "--oc",
        action="store_true",
        help="In watch mode, re-run only tests affected by changed files",
    )
    parser.add_argument(
        "--maxTargetsPerWorker",
        "--mtpw",
        type=int,
        default=0,
        help="Maximum targets to assign to a single worker when running in parallel (0 = unlimited)",
    )


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        "--rt",
        type=Path,
        default=None,
        help="Project root to run tests from (default: current directory)",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        metavar="target",
        help="Module, package, or path to test (default: tests)",
    )
    parser.add_argument(
        "--pattern",
        "--p",
        default="test*.py",
        help="Filename pattern when discovering directories (default: %(default)s)",
    )
    parser.add_argument(
        "--pattern-exclude",
        "--pe",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Glob pattern(s) to exclude from discovery",
    )
    parser.add_argument(
        "--ignore",
        "--ig",
        action="append",
        default=[],
        metavar="PATH",
        help="Directory or file paths to ignore during discovery",
    )


def _add_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--failfast", "--ff", action="store_true", help="Stop on first failure")
    parser.add_argument("--bail", "--b", action="store_true", help="Alias for --failfast")
    parser.add_argument(
        "--runInBand",
        "--rib",
        action="store_true",
        help="Run tests serially (default; reserved for future parallelism)",
    )
    parser.add_argument(
        "--maxWorkers",
        "--mw",
        type=int,
        default=1,
        help="Maximum workers (reserved; currently must be 1)",
    )
    parser.add_argument(
        "--updateSnapshot",
        "--us",
        action="store_true",
        help="Parse snapshot update flag (reserved for future snapshot support)",
    )
    parser.add_argument(
        "--snapshot-summary",
        "--ss",
        action="store_true",
        help="Show a snapshot create/update summary after a run",
    )
    parser.add_argument(
        "--coverage-bars",
        action="store_true",
        help="Show per-file coverage bars/sparklines when reporting coverage",
    )
    parser.add_argument(
        "--progress-fancy",
        "--pf",
        type=int,
        choices=[0, 1, 2],
        default=0,
        metavar="{0,1,2}",
        help="Fancy progress level: 0 = basic checkmarks, 1 = compact one-line stats, 2 = framed with stats",
    )
    parser.add_argument(
        "--fancy-progress",
        action="store_const",
        const=2,
        dest="progress_fancy",
        help="Alias for --progress-fancy=2 (framed with stats)",
    )


def _add_coverage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--coverage",
        "--cov",
        dest="coverage",
        action="store_true",
        help="Collect coverage with coverage.py (if installed)",
    )
    parser.add_argument(
        "--no-coverage",
        "--no-cov",
        dest="coverage",
        action="store_false",
        help="Disable coverage collection",
    )
    parser.add_argument(
        "--coverage-html",
        "--cov-html",
        nargs="?",
        const="coverage_html",
        default=None,
        metavar="DIR",
        help="Write HTML coverage report to DIR (default: coverage_html)",
    )
    parser.add_argument(
        "--coverage-threshold",
        "--cov-thresh",
        type=float,
        default=None,
        metavar="PCT",
        help="Fail if total coverage percentage is below this value",
    )
    parser.set_defaults(coverage=False)


def _add_reporting_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--report-format",
        "--rf",
        nargs="+",
        choices=["console", "json", "tap", "junit"],
        default=["console"],
        help="Additional report formats to write (console always shown)",
    )
    parser.add_argument(
        "--report-modules",
        "--rm",
        action="store_true",
        help="Show per-module/class test breakdowns above the summary (default on)",
    )
    parser.add_argument(
        "--no-report-modules",
        "--nrm",
        action="store_false",
        dest="report_modules",
        help="Hide per-module/class test breakdowns",
    )
    parser.add_argument(
        "--report-suite-table",
        "--rst",
        action="store_true",
        help="Show compact per-suite table in the console output",
    )
    parser.add_argument(
        "--report-outliers",
        "--ro",
        action="store_true",
        help="Show fastest/slowest test sections in the console output",
    )
    parser.set_defaults(report_modules=True)


def _add_diff_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-diff-lines",
        "--mdl",
        type=int,
        default=200,
        help="Maximum diff lines to display in assertion failures (0 = unlimited)",
    )
    parser.add_argument(
        "--no-color-diffs",
        "--ncd",
        action="store_false",
        dest="color_diffs",
        help="Disable colorized inline diffs",
    )
    parser.set_defaults(color_diffs=True)

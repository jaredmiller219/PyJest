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
    parser.add_argument("--buffer", action="store_true", help="Buffer stdout/stderr during tests")
    return parser.parse_args(argv)


def _add_watch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for filesystem changes and re-run tests",
    )
    parser.add_argument(
        "--watch-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds when using --watch (default: %(default)s)",
    )
    parser.add_argument(
        "--watch-debounce",
        type=float,
        default=0.2,
        help="Extra debounce delay after a change is detected (default: %(default)s)",
    )
    parser.add_argument(
        "--run-failures-first",
        action="store_true",
        help="In watch mode, prioritize rerunning previously failing modules",
    )
    parser.add_argument(
        "--onlyChanged",
        action="store_true",
        help="In watch mode, re-run only tests affected by changed files",
    )


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
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
        default="test*.py",
        help="Filename pattern when discovering directories (default: %(default)s)",
    )


def _add_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--failfast", action="store_true", help="Stop on first failure")
    parser.add_argument("--bail", action="store_true", help="Alias for --failfast")
    parser.add_argument(
        "--runInBand",
        action="store_true",
        help="Run tests serially (default; reserved for future parallelism)",
    )
    parser.add_argument(
        "--maxWorkers",
        type=int,
        default=1,
        help="Maximum workers (reserved; currently must be 1)",
    )
    parser.add_argument(
        "--updateSnapshot",
        action="store_true",
        help="Parse snapshot update flag (reserved for future snapshot support)",
    )


def _add_coverage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--coverage",
        dest="coverage",
        action="store_true",
        help="Collect coverage with coverage.py (if installed)",
    )
    parser.add_argument(
        "--no-coverage",
        dest="coverage",
        action="store_false",
        help="Disable coverage collection",
    )
    parser.add_argument(
        "--coverage-html",
        nargs="?",
        const="coverage_html",
        default=None,
        metavar="DIR",
        help="Write HTML coverage report to DIR (default: coverage_html)",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=None,
        metavar="PCT",
        help="Fail if total coverage percentage is below this value",
    )
    parser.set_defaults(coverage=False)

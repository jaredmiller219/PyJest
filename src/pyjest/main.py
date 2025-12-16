"""Entrypoint wiring for PyJest CLI."""

from __future__ import annotations

import sys
from typing import Sequence

from .assertions import expect, expect_async
from .cli import parse_args
from .discovery import mark_pyjest, marked_modules
from .orchestrator.env import prepare_environment
from .orchestrator.run_once import run_once
from .orchestrator.watch_loop import run_watch

__all__ = ["expect", "expect_async", "mark_pyjest", "marked_modules", "main"]


def main(argv: Sequence[str] | None = None) -> int:
    args = _prepare_args(argv)
    prepare_environment(args)
    return run_once(args) if not args.watch else run_watch(args)


def _prepare_args(argv: Sequence[str] | None) -> object:
    args = parse_args(argv or sys.argv[1:])
    args.failfast = args.failfast or args.bail
    if args.maxWorkers < 1:
        raise SystemExit("--maxWorkers must be >= 1")
    if args.maxTargetsPerWorker < 0:
        raise SystemExit("--maxTargetsPerWorker must be >= 0")
    if args.rerun < 0:
        raise SystemExit("--rerun must be >= 0")
    if args.coverage_html is not None or args.coverage_threshold is not None:
        args.coverage = True
    if args.coverage_json is not None:
        args.coverage = True
    args.coverage_threshold_module = _parse_module_thresholds(args.coverage_threshold_module)
    if "console" not in args.report_format:
        args.report_format.append("console")
    return args


def _parse_module_thresholds(entries: Sequence[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for entry in entries:
        if "=" not in entry:
            raise SystemExit(f"--coverage-threshold-module must be NAME=PCT, got: {entry}")
        name, pct_str = entry.split("=", 1)
        try:
            pct = float(pct_str)
        except ValueError:
            raise SystemExit(f"--coverage-threshold-module percent must be a number, got: {pct_str}") from None
        parsed[name] = pct
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())

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
    if args.coverage_html is not None or args.coverage_threshold is not None:
        args.coverage = True
    return args


if __name__ == "__main__":
    raise SystemExit(main())

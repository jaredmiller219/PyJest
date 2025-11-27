"""Entrypoint wiring for PyJest CLI."""

from __future__ import annotations

import sys
from typing import Sequence

from .assertions import expect, expect_async
from .cli import parse_args
from .discovery import mark_pyjest, marked_modules
from .orchestrator import prepare_environment, run_once, run_watch

__all__ = ["expect", "expect_async", "mark_pyjest", "marked_modules", "main"]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    args.failfast = args.failfast or args.bail
    if args.maxWorkers < 1:
        raise SystemExit("--maxWorkers must be >= 1")
    if args.coverage_html is not None or args.coverage_threshold is not None:
        args.coverage = True
    prepare_environment(args)
    if not args.watch:
        return run_once(args)
    return run_watch(args)


if __name__ == "__main__":
    raise SystemExit(main())

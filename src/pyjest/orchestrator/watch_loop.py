"""Watch-mode orchestration."""

from __future__ import annotations

import time
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from ..watch import detect_changes, snapshot_watchable_files, targets_from_changed, has_fast_watcher, next_change
from ..change_map import infer_targets_from_changes
from ..coverage_support import coverage_threshold_failed
from .runner import record_watch_outcome, run_suite


def run_watch(args) -> int:
    ctx = _initial_watch_context(args)
    try:
        return _watch_loop(ctx, args)
    except KeyboardInterrupt:
        print("\nWatch mode interrupted. Exiting.")
        return 0 if not ctx.last_fail else 1


def _watch_loop(ctx: "WatchContext", args) -> int:
    while True:
        _update_outcome(ctx, args)
        _sleep_until_change(ctx, args)
        _retarget_after_change(ctx, args)


def _update_outcome(ctx: "WatchContext", args) -> None:
    ctx.last_fail, ctx.failed_targets, ctx.last_failure_detail = _run_watch_iteration(ctx, args)
    _print_failure_recap(ctx)


def _sleep_until_change(ctx: "WatchContext", args) -> None:
    changed, snapshot = _wait_for_change(
        ctx.snapshot, ctx.root, args.watch_interval, args.watch_debounce
    )
    ctx.snapshot = snapshot
    ctx.last_changed = changed


def _retarget_after_change(ctx: "WatchContext", args) -> None:
    if not getattr(args, "watch_quiet", False):
        _print_change_notice(ctx.last_changed, ctx.root)
    ctx.targets = _next_targets(args, ctx.last_changed, ctx.failed_targets)


def _initial_watch_context(args) -> "WatchContext":
    root = args.root
    loader = unittest.TestLoader()
    snapshot = snapshot_watchable_files(root)
    targets = list(args.targets)
    return WatchContext(root=root, loader=loader, snapshot=snapshot, targets=targets, quiet=getattr(args, "watch_quiet", False))


def _run_watch_iteration(ctx: "WatchContext", args):
    result, coverage_percent, _ = run_suite(ctx.loader, args, ctx.targets)
    return record_watch_outcome(result, coverage_percent, args.coverage_threshold)


def _wait_for_change(
    snapshot: dict[Path, float], root: Path, interval: float, debounce: float
) -> tuple[set[Path], dict[Path, float]]:
    changed, snapshot = _wait_until_changed(snapshot, root, interval)
    if debounce:
        changed, snapshot = _apply_debounce(changed, snapshot, root, debounce)
    return changed, snapshot


def _wait_until_changed(snapshot: dict[Path, float], root: Path, interval: float) -> tuple[set[Path], dict[Path, float]]:
    if has_fast_watcher():
        return next_change(snapshot, root, interval)
    changed: set[Path] = set()
    while not changed:
        changed, snapshot = detect_changes(snapshot, root)
        if changed:
            break
        time.sleep(interval)
    return changed, snapshot


def _apply_debounce(changed: set[Path], snapshot: dict[Path, float], root: Path, debounce: float):
    time.sleep(debounce)
    extra, snapshot = detect_changes(snapshot, root)
    changed |= extra
    return changed, snapshot


def _print_change_notice(changed: set[Path], root: Path) -> None:
    display = ", ".join(str(path.relative_to(root)) for path in sorted(changed)) if changed else "unknown"
    print(f"\nChange detected: {display}")


def _print_failure_recap(ctx: "WatchContext") -> None:
    if getattr(ctx, "quiet", False):
        return
    if not ctx.last_fail:
        return
    failures = ", ".join(ctx.failed_targets) if ctx.failed_targets else "unknown modules"
    detail = f" ({ctx.last_failure_detail})" if ctx.last_failure_detail else ""
    print(f"Last run failed in: {failures}{detail}")
    print("Tip: rerun failed modules first with --run-failures-first.")


def _next_targets(args, changed: set[Path], failed_targets: Sequence[str]) -> list[str]:
    if args.onlyChanged:
        return targets_from_changed(changed, args.targets)
    if args.run_failures_first and failed_targets:
        return list(failed_targets)
    return infer_targets_from_changes(changed, args.targets)


@dataclass
class WatchContext:
    root: Path
    loader: unittest.TestLoader
    snapshot: dict[Path, float]
    targets: list[str]
    failed_targets: list[str] = field(default_factory=list)
    last_fail: bool = False
    last_changed: set[Path] = field(default_factory=set)
    last_failure_detail: str | None = None
    quiet: bool = False

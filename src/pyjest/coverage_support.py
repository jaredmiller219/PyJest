"""coverage.py integration helpers."""

from __future__ import annotations

import io
import builtins
import importlib
import os
import sys
from pathlib import Path
from typing import Any

from .colors import BRIGHT_GREEN, BRIGHT_RED, BRIGHT_YELLOW, color


def make_coverage(root: Path):
    coverage_module = _import_coverage()
    return coverage_module.Coverage(branch=True, source=[str(root)])


def report_coverage(cov: Any, html_dir: str | None, show_bars: bool = False) -> float:
    percent = _write_text_report(cov)
    if show_bars:
        _print_file_highlights(cov)
    _maybe_write_html(cov, html_dir)
    return float(percent)


def coverage_threshold_failed(percent: float | None, threshold: float | None) -> bool:
    if threshold is None or percent is None:
        return False
    if percent >= threshold:
        return False
    message = f"Coverage threshold not met: {percent:.2f}% < {threshold:.2f}%"
    print(color(message, BRIGHT_RED))
    return True


def _import_coverage():
    try:
        import coverage  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised in CLI usage
        raise SystemExit("coverage.py is required for --coverage. Install 'coverage' first.") from exc
    except Exception as exc:  # pragma: no cover - defensive for broken installs
        fallback = _retry_without_c_extension(exc)
        if fallback:
            return fallback
        raise SystemExit(f"coverage.py is installed but failed to import: {exc}") from exc
    return coverage


def _retry_without_c_extension(exc: Exception):
    """Try to import coverage.py without its C extension when it is broken.

    Some Python prereleases (for example 3.13 alphas) can load an incompatible
    ``coverage.tracer`` binary wheel, which raises SystemError on import. In
    that case, fall back to the slower pure-Python tracer so ``--coverage`` can
    still run instead of aborting.
    """

    if "coverage.tracer" not in str(exc):
        return None

    # Remove any half-imported modules from sys.modules so the retry starts clean.
    sys.modules.pop("coverage", None)
    sys.modules.pop("coverage.tracer", None)

    # Force coverage to select the pure-Python tracer instead of the C extension.
    os.environ.setdefault("COVERAGE_CORE", "pytrace")

    real_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "coverage.tracer":
            try:
                return real_import(name, globals, locals, fromlist, level)
            except Exception as tracer_exc:
                # Convert any failure to ImportError so coverage falls back.
                raise ImportError(tracer_exc) from tracer_exc
        return real_import(name, globals, locals, fromlist, level)

    try:
        builtins.__import__ = _guarded_import
        return importlib.import_module("coverage")
    except Exception:
        # If the retry also fails, let the original error surface.
        return None
    finally:
        builtins.__import__ = real_import


def _write_text_report(cov: Any) -> float:
    buffer = io.StringIO()
    percent = cov.report(skip_empty=True, file=buffer)
    report_text = buffer.getvalue().strip()
    if report_text:
        print(report_text)
    return float(percent)


def _maybe_write_html(cov: Any, html_dir: str | None) -> None:
    if not html_dir:
        return
    output_dir = Path(html_dir).resolve()
    cov.html_report(directory=str(output_dir))
    print(f"HTML coverage report written to {output_dir}")


def _print_file_highlights(cov: Any, width: int = 20) -> None:
    stats = _collect_file_stats(cov)
    if not stats:
        return
    stats_sorted = sorted(stats, key=lambda item: item["percent"], reverse=True)
    top = stats_sorted[:3]
    bottom = stats_sorted[-3:]
    print("Coverage file highlights:")
    seen: set[str] = set()
    for entry in top + bottom:
        key = entry["filename"]
        if key in seen:
            continue
        seen.add(key)
        bar = _render_bar(entry["percent"], width)
        print(f"  {bar} {entry['percent']:6.2f}% {entry['filename']}")


def _collect_file_stats(cov: Any) -> list[dict[str, Any]]:
    data = cov.get_data()
    stats: list[dict[str, Any]] = []
    for filename in sorted(data.measured_files()):
        try:
            _, statements, missing, _, _ = cov.analysis2(filename)
        except Exception:
            continue
        if not statements:
            continue
        covered = len(statements) - len(missing)
        percent = (covered / len(statements)) * 100 if statements else 0.0
        stats.append({"filename": filename, "percent": percent})
    return stats


def _render_bar(percent: float, width: int) -> str:
    filled = max(0, min(width, int((percent / 100.0) * width)))
    empty = width - filled
    bar = "█" * filled + "░" * empty
    if percent >= 90:
        clr = BRIGHT_GREEN
    elif percent >= 70:
        clr = BRIGHT_YELLOW
    else:
        clr = BRIGHT_RED
    return color(bar, clr)

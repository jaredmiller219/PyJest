"""coverage.py integration helpers."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any


def make_coverage(root: Path):
    coverage_module = _import_coverage()
    return coverage_module.Coverage(branch=True, source=[str(root)])


def report_coverage(cov: Any, html_dir: str | None) -> float:
    percent = _write_text_report(cov)
    _maybe_write_html(cov, html_dir)
    return float(percent)


def coverage_threshold_failed(percent: float | None, threshold: float | None) -> bool:
    if threshold is None or percent is None:
        return False
    if percent >= threshold:
        return False
    print(f"Coverage threshold not met: {percent:.2f}% < {threshold:.2f}%")
    return True


def _import_coverage():
    try:
        import coverage  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised in CLI usage
        raise SystemExit("coverage.py is required for --coverage. Install 'coverage' first.") from exc
    except Exception as exc:  # pragma: no cover - defensive for broken installs
        raise SystemExit(f"coverage.py is installed but failed to import: {exc}") from exc
    return coverage


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

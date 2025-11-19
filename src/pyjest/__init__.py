"""Custom unit test runner that mimics the high-level Jest CLI output.

The goal is not to be pixel perfect with Jest, but to provide a friendlier
experience than ``python -m unittest`` by printing colored per-test results and
succinct summaries. The script intentionally sticks to the standard library so
contributors do not have to install any extra tooling.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
from importlib.machinery import SourceFileLoader
import inspect
import os
import sys
import time
import unittest
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path.cwd()


def _set_project_root(root: Path) -> None:
    """Record and expose the working tree that contains the tests under run."""
    global PROJECT_ROOT
    PROJECT_ROOT = root.resolve()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


_set_project_root(PROJECT_ROOT)


_MARKED_MODULES: set[str] = set()


def mark_pyjest(module: str | None = None) -> None:
    """Record that a module expects to run under PyJest."""
    if module is None:
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        module = caller.f_globals.get("__name__", "<unknown>") if caller else "<unknown>"
    _MARKED_MODULES.add(module)


def marked_modules() -> tuple[str, ...]:
    """Return the modules that have explicitly opted into PyJest."""
    return tuple(sorted(_MARKED_MODULES))


def _pyjest_matches_pattern(path: Path, pattern: str) -> bool:
    """Return True if a .pyjest file logically matches the discovery pattern."""
    pretend_py = path.with_suffix(".py").name
    return fnmatch.fnmatch(pretend_py, pattern)


def _load_tests_from_pyjest_file(loader: unittest.TestLoader, path: Path) -> unittest.TestSuite:
    module_name = _module_name_from_path(path)
    loader_obj = SourceFileLoader(module_name, str(path))
    spec = importlib.util.spec_from_loader(module_name, loader_obj)
    if spec is None:
        raise ImportError(f"Cannot import PyJest test module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader_obj.exec_module(module)
    return loader.loadTestsFromModule(module)


def _discover_pyjest_files(loader: unittest.TestLoader, directory: Path, pattern: str) -> list[unittest.TestSuite]:
    suites: list[unittest.TestSuite] = []
    for file in sorted(directory.rglob("*.pyjest")):
        if not _pyjest_matches_pattern(file, pattern):
            continue
        suites.append(_load_tests_from_pyjest_file(loader, file))
    return suites


def _load_directory_suite(loader: unittest.TestLoader, directory: Path, pattern: str) -> unittest.TestSuite:
    base_suite = loader.discover(str(directory), pattern=pattern)
    extra = _discover_pyjest_files(loader, directory, pattern)
    if not extra:
        return base_suite
    suites: list[unittest.TestSuite] = [base_suite]
    suites.extend(extra)
    return unittest.TestSuite(suites)


def _is_python_project(root: Path) -> bool:
    markers = ["pyproject.toml", "setup.cfg", "setup.py", "requirements.txt"]
    if any((root / marker).exists() for marker in markers):
        return True
    return any(root.glob("*.py"))


def _ensure_python_project(root: Path) -> None:
    if not _is_python_project(root):
        raise SystemExit(
            "This directory is not a Python/PyJest project.\n"
            "Run pyjest from a project root with a pyproject and .py/.pyjest tests,\n"
            "or pass --root to point at one."
        )


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GREY = "\033[90m"
BG_GREEN = "\033[42m"
FG_WHITE = "\033[97m"
BG_RED = "\033[41m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_RED = "\033[91m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_CYAN = "\033[96m"


def _color(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def _doc_summary(doc: str | None) -> str | None:
    if not doc:
        return None
    cleaned = inspect.cleandoc(doc).strip()
    if not cleaned:
        return None
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _module_display(module_name: str) -> tuple[str, str | None]:
    module = sys.modules.get(module_name)
    doc_title = _doc_summary(getattr(module, "__doc__", None)) if module else None
    if module and hasattr(module, "__file__") and module.__file__:
        path = Path(module.__file__).resolve()
        try:
            rel = path.relative_to(PROJECT_ROOT)
            return str(rel), doc_title
        except ValueError:
            return str(path), doc_title
    return module_name, doc_title


def _format_test_name(test: unittest.case.TestCase) -> str:
    """Return a dotted identifier suitable for error sections."""
    test_id = test.id()
    parts = test_id.split(".")
    if len(parts) >= 3:
        module = ".".join(parts[:-2])
        cls = parts[-2]
        method = parts[-1]
        return f"{module}.{cls}.{method}"
    return test_id


def _format_test_title(test: unittest.case.TestCase) -> str:
    description = test.shortDescription()
    if description:
        return description.strip()
    raw = getattr(test, "_testMethodName", test.id())
    return raw.replace("_", " ").strip()


@dataclass
class TestDetail:
    name: str
    status: str
    duration: float
    summary: str | None = None
    note: str | None = None
    detail: str | None = None


@dataclass
class ClassGroup:
    name: str
    doc_title: str | None
    tests: list[TestDetail] = field(default_factory=list)


@dataclass
class ModuleReport:
    key: str
    display: str
    doc_title: str | None
    counts: Counter = field(default_factory=Counter)
    groups: dict[str, ClassGroup] = field(default_factory=dict)
    group_order: list[str] = field(default_factory=list)

    def register(self, class_name: str, class_doc_title: str | None, detail: TestDetail) -> None:
        if class_name not in self.groups:
            self.groups[class_name] = ClassGroup(name=class_name, doc_title=class_doc_title)
            self.group_order.append(class_name)
        self.groups[class_name].tests.append(detail)
        self.counts[detail.status] += 1

    @property
    def headline_status(self) -> str:
        if self.counts.get("FAIL") or self.counts.get("ERROR"):
            return "FAIL"
        if self.counts.get("SKIP") and not self.counts.get("PASS"):
            return "SKIP"
        return "PASS"


class JestStyleResult(unittest.TestResult):
    """Custom ``unittest`` result object that prints Jest-like progress."""

    def __init__(self, stream, descriptions, verbosity):  # type: ignore[override]
        super().__init__()
        self.stream = stream
        self.descriptions = descriptions
        self.verbosity = verbosity
        self._start_times: dict[unittest.case.TestCase, float] = {}
        self._successes: list[unittest.case.TestCase] = []
        self._failures_detail: list[tuple[unittest.case.TestCase, str]] = []
        self._errors_detail: list[tuple[unittest.case.TestCase, str]] = []
        self._skips_detail: list[tuple[unittest.case.TestCase, str]] = []
        self._expected_failures: list[tuple[unittest.case.TestCase, str]] = []
        self._unexpected_successes: list[unittest.case.TestCase] = []
        self._module_reports: dict[str, ModuleReport] = {}
        self._module_order: list[str] = []

    @property
    def successes(self) -> Sequence[unittest.case.TestCase]:
        return tuple(self._successes)

    def startTest(self, test):  # type: ignore[override]
        self._start_times[test] = time.perf_counter()
        super().startTest(test)

    def _elapsed(self, test: unittest.case.TestCase) -> float:
        start = self._start_times.pop(test, None)
        if start is None:
            return 0.0
        return time.perf_counter() - start

    def _module_report_for(self, test: unittest.case.TestCase) -> ModuleReport:
        module_name = test.__class__.__module__
        if module_name not in self._module_reports:
            display, doc_title = _module_display(module_name)
            self._module_reports[module_name] = ModuleReport(
                key=module_name,
                display=display,
                doc_title=doc_title,
            )
            self._module_order.append(module_name)
        return self._module_reports[module_name]

    def _add_detail(
        self,
        test: unittest.case.TestCase,
        status: str,
        duration: float,
        *,
        note: str | None = None,
        detail: str | None = None,
    ) -> None:
        report = self._module_report_for(test)
        summary = _doc_summary(getattr(test, "_testMethodDoc", None))
        title = summary or _format_test_title(test)
        cls = test.__class__
        class_name = cls.__name__
        class_doc_title = _doc_summary(getattr(cls, "__doc__", None))
        report.register(
            class_name,
            class_doc_title,
            TestDetail(name=title, status=status, duration=duration, summary=summary, note=note, detail=detail),
        )

    def print_module_reports(self) -> None:
        status_colors = {"PASS": BRIGHT_GREEN, "FAIL": BRIGHT_RED, "SKIP": BRIGHT_YELLOW}
        detail_colors = {
            "PASS": BRIGHT_GREEN,
            "FAIL": BRIGHT_RED,
            "ERROR": BRIGHT_RED,
            "SKIP": BRIGHT_YELLOW,
            "XF": BRIGHT_YELLOW,
            "XPASS": BRIGHT_CYAN,
        }
        icon_map = {
            "PASS": _color("✓", BRIGHT_GREEN),
            "FAIL": _color("✕", BRIGHT_RED),
            "ERROR": _color("✕", BRIGHT_RED),
            "SKIP": _color("↷", BRIGHT_YELLOW),
            "XF": _color("≒", BRIGHT_YELLOW),
            "XPASS": _color("★", BRIGHT_CYAN),
        }
        self.stream.writeln("")
        for module_name in self._module_order:
            report = self._module_reports[module_name]
            status = report.headline_status
            color = status_colors.get(status, CYAN)
            if status == "PASS":
                badge = f"{BG_GREEN}{FG_WHITE}{BOLD} {status} {RESET}"
            elif status == "FAIL":
                badge = f"{BG_RED}{FG_WHITE}{BOLD} {status} {RESET}"
            else:
                badge = _color(f" {status} ", color)
            path = Path(report.display)
            dimmed = str(path.parent) if path.parent != Path('.') else ''
            filename = path.name
            if dimmed:
                display = f"{DIM}{dimmed}/{RESET}{_color(filename, BOLD)}"
            else:
                display = _color(filename, BOLD)
            self.stream.writeln(f"{badge} {display}")
            for class_name in report.group_order:
                group = report.groups[class_name]
                description = group.doc_title or class_name
                class_line = f"  {_color('›', BRIGHT_CYAN)} {description}"
                self.stream.writeln(class_line)
                for detail in group.tests:
                    icon = icon_map.get(detail.status, _color("•", CYAN))
                    duration_ms = f"{detail.duration * 1000:.0f} ms"
                    status_color = detail_colors.get(detail.status, CYAN)
                    text_color = DIM
                    if detail.status in {"FAIL", "ERROR"}:
                        text_color = status_color
                    line = f"    {icon} {_color(detail.name, text_color)} {DIM}({duration_ms}){RESET}"
                    if detail.note:
                        line += f" {DIM}[{detail.note}]{RESET}"
                    self.stream.writeln(line)
                    if detail.summary and detail.summary != detail.name:
                        self.stream.writeln(f"      {DIM}{detail.summary}{RESET}")
                    if detail.detail and detail.status in {"FAIL", "ERROR"}:
                        for extra_line in detail.detail.splitlines():
                            self.stream.writeln(f"      {extra_line}")
                self.stream.writeln("")

    def addSuccess(self, test):  # type: ignore[override]
        super().addSuccess(test)
        duration = self._elapsed(test)
        self._successes.append(test)
        self._add_detail(test, "PASS", duration)

    def addFailure(self, test, err):  # type: ignore[override]
        super().addFailure(test, err)
        duration = self._elapsed(test)
        formatted = self._exc_info_to_string(err, test)
        self._failures_detail.append((test, formatted))
        self._add_detail(test, "FAIL", duration, detail=formatted)

    def addError(self, test, err):  # type: ignore[override]
        super().addError(test, err)
        duration = self._elapsed(test)
        formatted = self._exc_info_to_string(err, test)
        self._errors_detail.append((test, formatted))
        self._add_detail(test, "ERROR", duration, detail=formatted)

    def addSkip(self, test, reason):  # type: ignore[override]
        super().addSkip(test, reason)
        duration = self._elapsed(test)
        self._skips_detail.append((test, reason))
        self._add_detail(test, "SKIP", duration, note=reason)

    def addExpectedFailure(self, test, err):  # type: ignore[override]
        super().addExpectedFailure(test, err)
        self._expected_failures.append((test, self._exc_info_to_string(err, test)))
        duration = self._elapsed(test)
        self._add_detail(test, "XF", duration)

    def addUnexpectedSuccess(self, test):  # type: ignore[override]
        super().addUnexpectedSuccess(test)
        duration = self._elapsed(test)
        self._unexpected_successes.append(test)
        self._add_detail(test, "XPASS", duration)

    def printErrors(self):  # type: ignore[override]
        sections = [
            ("Failures", self._failures_detail),
            ("Errors", self._errors_detail),
        ]
        printed_header = False
        for title, entries in sections:
            if not entries:
                continue
            if not printed_header:
                self.stream.writeln("")
                printed_header = True
            header = f"{BG_RED}{FG_WHITE}{BOLD} {title.upper()} {RESET}"
            self.stream.writeln(header)
            for test, err in entries:
                module_name = test.__class__.__module__
                file_display, _ = _module_display(module_name)
                test_title = _format_test_title(test)
                pointer = _color("›", BRIGHT_CYAN)
                self.stream.writeln(
                    f"  {_color('✕', BRIGHT_RED)} {DIM}{file_display}{RESET} {pointer} "
                    f"{_color(test_title, BRIGHT_RED)}"
                )
                indented = "\n".join(f"      {line}" for line in err.splitlines())
                self.stream.writeln(indented)
                self.stream.writeln("")


class JestStyleTestRunner(unittest.TextTestRunner):
    resultclass = JestStyleResult

    def __init__(self, **kwargs):
        super().__init__(verbosity=2, **kwargs)

    def run(self, test):  # type: ignore[override]
        result = self._makeResult()
        result.failfast = self.failfast
        result.buffer = self.buffer
        start_time = time.perf_counter()

        result.startTestRun()
        try:
            test(result)
        finally:
            result.stopTestRun()

        duration = time.perf_counter() - start_time
        result.print_module_reports()
        result.printErrors()
        self._print_summary(result, duration)
        return result

    def _print_summary(self, result: JestStyleResult, duration: float) -> None:
        passed = len(result.successes)
        failed = len(result.failures)
        errored = len(result.errors)
        skipped = len(result.skipped)
        total = result.testsRun
        suites_total = len(result._module_reports)
        suites_failed = sum(
            1 for report in result._module_reports.values() if report.headline_status == "FAIL"
        )
        suites_passed = sum(
            1 for report in result._module_reports.values() if report.headline_status == "PASS"
        )
        suites_skipped = suites_total - suites_failed - suites_passed

        if failed or errored:
            badge = _color(" FAIL ", BRIGHT_RED)
            title = _color("Test suites failing", BOLD)
        else:
            badge = f"{BG_GREEN}{FG_WHITE}{BOLD} PASS {RESET}"
            title = _color("Test suites complete", BOLD)

        self.stream.writeln("")
        self.stream.writeln(f"{badge} {title}")

        def fmt(value: int, label: str, color: str) -> str | None:
            if value == 0:
                return None
            return _color(f"{value} {label}", color)

        suite_parts = [
            fmt(suites_failed, "failed", BRIGHT_RED),
            fmt(suites_passed, "passed", BRIGHT_GREEN),
            fmt(suites_skipped, "skipped", BRIGHT_YELLOW),
        ]
        suite_parts = [part for part in suite_parts if part]
        suite_parts.append(f"{suites_total} total")
        suite_summary = ", ".join(suite_parts)

        test_parts = [
            fmt(failed + errored, "failed", BRIGHT_RED),
            fmt(passed, "passed", BRIGHT_GREEN),
            fmt(skipped, "skipped", BRIGHT_YELLOW),
        ]
        test_parts = [part for part in test_parts if part]
        test_parts.append(f"{total} total")
        test_summary = ", ".join(test_parts)

        self.stream.writeln(f"  Test Suites: {suite_summary}")
        self.stream.writeln(f"  Tests:       {test_summary}")
        self.stream.writeln(f"  Time:        {duration:.2f}s")


def _module_name_from_path(path: Path) -> str:
    rel = path.resolve()
    try:
        rel = rel.relative_to(PROJECT_ROOT)
    except ValueError:
        return path.stem
    module = ".".join(rel.with_suffix("").parts)
    return module


def _load_targets(
    loader: unittest.TestLoader, targets: Sequence[str], pattern: str
) -> unittest.TestSuite:
    if not targets:
        tests_dir = Path("tests")
        if tests_dir.exists():
            return _load_directory_suite(loader, tests_dir, pattern)
        raise SystemExit("no pyjest file(s) exists")

    suites: list[unittest.TestSuite] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            if not any(path.rglob("*.py")) and not any(path.rglob("*.pyjest")):
                raise SystemExit(
                    f"pyjest only runs Python tests. Directory '{path}' has no .py or .pyjest files."
                )
            suites.append(_load_directory_suite(loader, path, pattern))
            continue
        if path.is_file():
            if path.suffix not in {".py", ".pyjest"}:
                raise SystemExit(f"pyjest can only run Python files: '{path}'")
            if path.suffix == ".pyjest":
                suites.append(_load_tests_from_pyjest_file(loader, path))
                continue
            if path.suffix == ".py":
                raise SystemExit(
                    f"'{path}' is not a .pyjest file. Rename it to end with .pyjest or pass an importable module path."
                )
        suites.append(loader.loadTestsFromName(target))
    return unittest.TestSuite(suites)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the test suite with Jest-style output."
    )
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
    parser.add_argument("--failfast", action="store_true", help="Stop on first failure")
    parser.add_argument("--buffer", action="store_true", help="Buffer stdout/stderr during tests")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = (args.root or Path.cwd()).expanduser().resolve()
    if args.root:
        os.chdir(root)
    _set_project_root(root)
    _ensure_python_project(root)
    loader = unittest.TestLoader()
    suite = _load_targets(loader, args.targets, args.pattern)
    runner = JestStyleTestRunner(failfast=args.failfast, buffer=args.buffer, stream=sys.stdout)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

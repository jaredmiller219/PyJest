"""Jest-style reporter and test runner."""

from __future__ import annotations

import time
import unittest
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .colors import (
    BG_GREEN,
    BG_RED,
    BOLD,
    BRIGHT_CYAN,
    BRIGHT_GREEN,
    BRIGHT_RED,
    BRIGHT_YELLOW,
    CYAN,
    DIM,
    FG_WHITE,
    GREY,
    RESET,
    YELLOW,
    color,
)
from .discovery import _doc_summary, _format_test_name, _format_test_title, _module_display


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
        self._progress_started = False

    @property
    def successes(self) -> Sequence[unittest.case.TestCase]:
        return tuple(self._successes)

    def startTestRun(self):  # type: ignore[override]
        super().startTestRun()
        self.stream.writeln("Running tests...")
        self._progress_started = True

    def _write_progress(self, icon: str) -> None:
        if not self._progress_started:
            return
        self.stream.write(icon)
        self.stream.flush()

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
        from .colors import BRIGHT_GREEN, BRIGHT_RED, BRIGHT_YELLOW, BRIGHT_CYAN  # local import to avoid cycles

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
            "PASS": color("✓", BRIGHT_GREEN),
            "FAIL": color("✕", BRIGHT_RED),
            "ERROR": color("✕", BRIGHT_RED),
            "SKIP": color("↷", BRIGHT_YELLOW),
            "XF": color("≒", BRIGHT_YELLOW),
            "XPASS": color("★", BRIGHT_CYAN),
        }
        self.stream.writeln("")
        for module_name in self._module_order:
            report = self._module_reports[module_name]
            status = report.headline_status
            clr = status_colors.get(status, CYAN)
            if status == "PASS":
                badge = f"{BG_GREEN}{FG_WHITE}{BOLD} {status} {RESET}"
            elif status == "FAIL":
                badge = f"{BG_RED}{FG_WHITE}{BOLD} {status} {RESET}"
            else:
                badge = color(f" {status} ", clr)
            path = Path(report.display)
            dimmed = str(path.parent) if path.parent != Path(".") else ""
            filename = path.name
            if dimmed:
                display = f"{DIM}{dimmed}/{RESET}{color(filename, BOLD)}"
            else:
                display = color(filename, BOLD)
            self.stream.writeln(f"{badge} {display}")
            for class_name in report.group_order:
                group = report.groups[class_name]
                description = group.doc_title or class_name
                class_line = f"  {color('›', BRIGHT_CYAN)} {description}"
                self.stream.writeln(class_line)
                for detail in group.tests:
                    icon = icon_map.get(detail.status, color("•", CYAN))
                    duration_ms = f"{detail.duration * 1000:.0f} ms"
                    status_color = detail_colors.get(detail.status, CYAN)
                    text_color = DIM
                    if detail.status in {"FAIL", "ERROR"}:
                        text_color = status_color
                    line = f"    {icon} {color(detail.name, text_color)} {DIM}({duration_ms}){RESET}"
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
        self._write_progress(color("✓", BRIGHT_GREEN))

    def addFailure(self, test, err):  # type: ignore[override]
        super().addFailure(test, err)
        duration = self._elapsed(test)
        formatted = self._exc_info_to_string(err, test)
        self._failures_detail.append((test, formatted))
        self._add_detail(test, "FAIL", duration, detail=formatted)
        self._write_progress(color("✕", BRIGHT_RED))

    def addError(self, test, err):  # type: ignore[override]
        super().addError(test, err)
        duration = self._elapsed(test)
        formatted = self._exc_info_to_string(err, test)
        self._errors_detail.append((test, formatted))
        self._add_detail(test, "ERROR", duration, detail=formatted)
        self._write_progress(color("✕", BRIGHT_RED))

    def addSkip(self, test, reason):  # type: ignore[override]
        super().addSkip(test, reason)
        duration = self._elapsed(test)
        self._skips_detail.append((test, reason))
        self._add_detail(test, "SKIP", duration, note=reason)
        self._write_progress(color("↷", BRIGHT_YELLOW))

    def addExpectedFailure(self, test, err):  # type: ignore[override]
        super().addExpectedFailure(test, err)
        self._expected_failures.append((test, self._exc_info_to_string(err, test)))
        duration = self._elapsed(test)
        self._add_detail(test, "XF", duration)
        self._write_progress(color("≒", BRIGHT_YELLOW))

    def addUnexpectedSuccess(self, test):  # type: ignore[override]
        super().addUnexpectedSuccess(test)
        duration = self._elapsed(test)
        self._unexpected_successes.append(test)
        self._add_detail(test, "XPASS", duration)
        self._write_progress(color("★", BRIGHT_CYAN))

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
                pointer = color("›", BRIGHT_CYAN)
                self.stream.writeln(
                    f"  {color('✕', BRIGHT_RED)} {DIM}{file_display}{RESET} {pointer} "
                    f"{color(test_title, BRIGHT_RED)}"
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

        # Drop a newline after the inline progress symbols.
        self.stream.writeln("")
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
            badge = color(" FAIL ", BRIGHT_RED)
            title = color("Test suites failing", BOLD)
        else:
            badge = f"{BG_GREEN}{FG_WHITE}{BOLD} PASS {RESET}"
            title = color("Test suites complete", BOLD)

        self.stream.writeln("")
        self.stream.writeln(f"{badge} {title}")

        def fmt(value: int, label: str, clr: str) -> str | None:
            if value == 0:
                return None
            return color(f"{value} {label}", clr)

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

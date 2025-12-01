"""Jest-style reporter and test runner."""

from __future__ import annotations

import time
import unittest
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Sequence

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
from .discovery import _doc_summary, _format_test_name, _module_display
from .snapshot import print_snapshot_summary


@dataclass
class TestDetail:
    name: str
    status: str
    duration: float
    summary: str | None = None
    note: str | None = None
    detail: str | None = None
    module: str | None = None
    cls: str | None = None


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
    total_duration: float = 0.0

    def register(self, class_name: str, class_doc_title: str | None, detail: TestDetail) -> None:
        if class_name not in self.groups:
            self.groups[class_name] = ClassGroup(name=class_name, doc_title=class_doc_title)
            self.group_order.append(class_name)
        self.groups[class_name].tests.append(detail)
        self.counts[detail.status] += 1
        self.total_duration += detail.duration

    @property
    def headline_status(self) -> str:
        if self.counts.get("FAIL") or self.counts.get("ERROR"):
            return "FAIL"
        if self.counts.get("SKIP") and not self.counts.get("PASS"):
            return "SKIP"
        return "PASS"


class JestStyleResult(unittest.TestResult):
    """Custom ``unittest`` result object that prints Jest-like progress."""

    def __init__(self, stream: IO[str], descriptions, verbosity):  # type: ignore[override]
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
        self._progress_start = 0.0
        self._progress_last = 0.0
        self._spinner_state = 0
        self._current_test: unittest.case.TestCase | None = None
        self._all_details: list[TestDetail] = []
        self.report_modules: bool = False
        self.report_suite_table: bool = False
        self.report_outliers: bool = False
        self.spinner_enabled: bool = True
        self._progress_counts: Counter[str] = Counter()
        self._status_line_len = 0
        self._inline_progress_total = 0
        self._tests_seen = 0
        self._last_test_label = ""
        self._recent_statuses: list[str] = []
        self._status_cycle: Counter[str] = Counter()
        self._inline_row_count = 0
        self._inline_border = "═" * 30
        self._inline_row_width = len(self._inline_border) - 2  # interior width
        self._inline_row_pos = 0
        self._inline_header_drawn = False
        self.progress_fancy_level: int = 0

    @property
    def successes(self) -> Sequence[unittest.case.TestCase]:
        return tuple(self._successes)

    def startTestRun(self):  # type: ignore[override]
        super().startTestRun()
        self.stream.writeln("Running tests...")
        self._progress_started = True
        self._progress_start = time.perf_counter()
        if not self.spinner_enabled and self.progress_fancy_level >= 1:
            self._write_inline_header()

    def _record_progress(self, status: str) -> None:
        if not self._progress_started:
            return
        self._progress_counts[status] += 1
        if self._current_test:
            module = self._current_test.__class__.__module__
            title = _explicit_label(self._current_test)
            self._last_test_label = f"{module}::{title}"
        self._recent_statuses.append(status)
        if len(self._recent_statuses) > 16:
            self._recent_statuses = self._recent_statuses[-16:]
        if self.spinner_enabled:
            self._write_status_line()
        else:
            self._write_progress_icon(status)

    def _write_status_line(self) -> None:
        if not self.spinner_enabled or not self._progress_started or not self._current_test:
            return
        now = time.perf_counter()
        if now - self._progress_last < 0.05:
            return
        self._progress_last = now
        elapsed = now - self._progress_start
        spinner = ["⣾", "⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽"][self._spinner_state % 8]
        self._spinner_state += 1
        module_name = self._current_test.__class__.__module__
        test_title = _explicit_label(self._current_test)
        pass_count = self._progress_counts.get("PASS", 0) + self._progress_counts.get("XPASS", 0)
        fail_count = self._progress_counts.get("FAIL", 0) + self._progress_counts.get("ERROR", 0)
        skip_count = self._progress_counts.get("SKIP", 0) + self._progress_counts.get("XF", 0)
        line = (
            f"\r{color(spinner, BRIGHT_CYAN)} {elapsed:5.1f}s "
            f"#{self._tests_seen:<3d} "
            f"{color('✓', BRIGHT_GREEN)} {pass_count} "
            f"{color('✕', BRIGHT_RED)} {fail_count} "
            f"{color('↷', BRIGHT_YELLOW)} {skip_count} "
            f"{color(module_name, DIM)} {test_title}"
        )
        padded = line.ljust(self._status_line_len or len(line))
        self._status_line_len = max(self._status_line_len, len(line))
        self.stream.write(padded)
        self.stream.flush()

    def _write_progress_icon(self, status: str) -> None:
        self._write_inline_header()
        icon = _icon_map().get(status, color("•", CYAN))
        # Level 0: basic inline checkmarks with no frame.
        if self.progress_fancy_level == 0:
            self.stream.write(f"{icon}\u2009")
            self._inline_progress_total += 1
            self.stream.flush()
            return
        self._inline_progress_total += 1
        if self._inline_row_pos == 0:
            self.stream.write(color("║ ", BRIGHT_CYAN))
        self.stream.write(icon)
        self._inline_row_pos += 1
        self._inline_row_count += 1
        if self._inline_row_pos >= self._inline_row_width:
            self._close_inline_row()
        self.stream.flush()

    def close_progress_block(self) -> None:
        if self.spinner_enabled or (not self._inline_progress_total and not self._inline_header_drawn):
            return
        if self.progress_fancy_level >= 1:
            if self._inline_row_pos:
                padding = max(0, self._inline_row_width - self._inline_row_pos)
                self.stream.write(" " * padding + color(" ║", BRIGHT_CYAN) + "\n")
                if self.progress_fancy_level >= 2:
                    self._write_progress_card()
                    self.stream.write(f"{color('╠' + self._inline_border + '╣', BRIGHT_CYAN)}\n")
                    self._inline_row_pos = 0
            self.stream.write(f"{color('╚' + self._inline_border + '╝', BRIGHT_CYAN)}\n")
        self.stream.flush()

    def _close_inline_row(self) -> None:
        padding = max(0, self._inline_row_width - self._inline_row_pos)
        self.stream.write(" " * padding + color(" ║", BRIGHT_CYAN) + "\n")
        if self.progress_fancy_level >= 2:
            self._write_progress_card()
        if self.progress_fancy_level >= 1:
            self.stream.write(f"{color('╠' + self._inline_border + '╣', BRIGHT_CYAN)}\n")
        self._inline_row_pos = 0
        self.stream.write(color("║ ", BRIGHT_CYAN))

    def _write_progress_card(self) -> None:
        summary = (
            f"{color('✓', BRIGHT_GREEN)} {self._progress_counts.get('PASS', 0) + self._progress_counts.get('XPASS', 0):<3}"
            f"{color('✕', BRIGHT_RED)} {self._progress_counts.get('FAIL', 0) + self._progress_counts.get('ERROR', 0):<3}"
            f"{color('↷', BRIGHT_YELLOW)} {self._progress_counts.get('SKIP', 0) + self._progress_counts.get('XF', 0):<3}"
            f"{color('#', CYAN)} {self._tests_seen:<3}"
        )
        label = (self._last_test_label or "n/a")[:24]
        trail = "".join(_icon_map().get(s, "•") for s in self._recent_statuses[-20:])
        self.stream.write(f"{color('║ stats:', BRIGHT_CYAN)} {summary:<20}{color('║', BRIGHT_CYAN)}\n")
        self.stream.write(f"{color('║ trail:', BRIGHT_CYAN)} {trail:<20}{color('║', BRIGHT_CYAN)}\n")
        self.stream.write(f"{color('║ last:', BRIGHT_CYAN)}  {color(label, DIM):<20}{color('║', BRIGHT_CYAN)}\n")

    def _write_inline_header(self) -> None:
        if self._inline_header_drawn or self.spinner_enabled or self.progress_fancy_level < 1:
            return
        legend_plain = "✓ pass  ✕ fail  ↷ skip"
        border_len = len(self._inline_border)
        left_pad = max(0, (border_len - len(legend_plain)) // 2)
        right_pad = max(0, border_len - len(legend_plain) - left_pad)
        legend_colored = (
            " " * left_pad
            + color("✓", BRIGHT_GREEN)
            + " pass  "
            + color("✕", BRIGHT_RED)
            + " fail  "
            + color("↷", BRIGHT_YELLOW)
            + " skip"
            + " " * right_pad
        )
        header = (
            f"\n{color('╔' + self._inline_border + '╗', BRIGHT_CYAN)}\n"
            f"{color('║' + ' Progress '.center(len(self._inline_border)) + '║', BRIGHT_CYAN)}\n"
            f"{color('╠' + ' Legend '.center(len(self._inline_border), '═') + '╣', BRIGHT_CYAN)}\n"
            f"{color('║', BRIGHT_CYAN)}{legend_colored}{color('║', BRIGHT_CYAN)}\n"
            f"{color('╠' + self._inline_border + '╣', BRIGHT_CYAN)}\n"
        )
        self.stream.write(header)
        self._inline_header_drawn = True


    def startTest(self, test):  # type: ignore[override]
        self._start_times[test] = time.perf_counter()
        self._current_test = test
        self._tests_seen += 1
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
        title = _explicit_label(test)
        cls = test.__class__
        class_label = getattr(cls, "__pyjest_describe__", None)
        class_name = class_label or cls.__name__
        class_doc_title = class_label or _doc_summary(getattr(cls, "__doc__", None))
        module_name = cls.__module__
        detail_obj = TestDetail(
            name=title,
            status=status,
            duration=duration,
            summary=summary,
            note=note,
            detail=detail,
            module=module_name,
            cls=class_name,
        )
        report.register(class_name, class_doc_title, detail_obj)
        self._all_details.append(detail_obj)

    def print_module_reports(self) -> None:
        if not (self.report_modules or self.report_suite_table or self.report_outliers):
            return
        status_colors = _status_colors()
        detail_colors = _detail_colors()
        icon_map = _icon_map()
        printed_any = False
        if self.report_modules:
            self.stream.writeln("")
            for module_name in self._module_order:
                report = self._module_reports[module_name]
                badge = _format_badge(report.headline_status, status_colors)
                display = _format_module_display(report.display)
                self.stream.writeln(f"{badge} {display}")
                for class_name in report.group_order:
                    group = report.groups[class_name]
                    self._print_group(group, detail_colors, icon_map)
                    self.stream.writeln("")
            printed_any = True
        if self.report_suite_table and self._module_order:
            if not printed_any:
                self.stream.writeln("")
            self._print_suite_table()
            printed_any = True
        if self.report_outliers and self._module_order:
            if not printed_any:
                self.stream.writeln("")
            self._print_outliers()

    def addSuccess(self, test):  # type: ignore[override]
        super().addSuccess(test)
        duration = self._elapsed(test)
        self._successes.append(test)
        self._add_detail(test, "PASS", duration)
        self._record_progress("PASS")

    def addFailure(self, test, err):  # type: ignore[override]
        super().addFailure(test, err)
        duration = self._elapsed(test)
        formatted = self._exc_info_to_string(err, test)
        self._failures_detail.append((test, formatted))
        self._add_detail(test, "FAIL", duration, detail=formatted)
        self._record_progress("FAIL")

    def addError(self, test, err):  # type: ignore[override]
        super().addError(test, err)
        duration = self._elapsed(test)
        formatted = self._exc_info_to_string(err, test)
        self._errors_detail.append((test, formatted))
        self._add_detail(test, "ERROR", duration, detail=formatted)
        self._record_progress("ERROR")

    def addSkip(self, test, reason):  # type: ignore[override]
        super().addSkip(test, reason)
        duration = self._elapsed(test)
        self._skips_detail.append((test, reason))
        self._add_detail(test, "SKIP", duration, note=reason)
        self._record_progress("SKIP")

    def addExpectedFailure(self, test, err):  # type: ignore[override]
        super().addExpectedFailure(test, err)
        self._expected_failures.append((test, self._exc_info_to_string(err, test)))
        duration = self._elapsed(test)
        self._add_detail(test, "XF", duration)
        self._record_progress("XF")

    def addUnexpectedSuccess(self, test):  # type: ignore[override]
        super().addUnexpectedSuccess(test)
        duration = self._elapsed(test)
        self._unexpected_successes.append(test)
        self._add_detail(test, "XPASS", duration)
        self._record_progress("XPASS")

    def printErrors(self):  # type: ignore[override]
        # Clear any lingering status line before printing details.
        if self._status_line_len:
            self.stream.write("\n")
            self._status_line_len = 0
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
                test_title = _explicit_label(test) or "<unnamed>"
                pointer = color("›", BRIGHT_CYAN)
                self.stream.writeln(
                    f"  {color('✕', BRIGHT_RED)} {DIM}{file_display}{RESET} {pointer} "
                    f"{color(test_title, BRIGHT_RED)}"
                )
                indented = "\n".join(f"      {line}" for line in err.splitlines())
                self.stream.writeln(indented)
                self.stream.writeln("")

    def _print_group(self, group: ClassGroup, detail_colors: dict[str, str], icon_map: dict[str, str]) -> None:
        description = group.doc_title or group.name
        class_line = f"  {color('›', BRIGHT_CYAN)} {description}"
        self.stream.writeln(class_line)
        for detail in group.tests:
            self._print_detail(detail, detail_colors, icon_map)

    def _print_detail(self, detail: TestDetail, detail_colors: dict[str, str], icon_map: dict[str, str]) -> None:
        if not detail.name:
            return
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

    def _print_suite_table(self) -> None:
        status_colors = _status_colors()
        header = f"{'Status':<8}{'Pass':>6}{'Fail':>6}{'Skip':>6}{'Time':>10}  Module"
        self.stream.writeln(header)
        self.stream.writeln("-" * len(header))
        for module_name in self._module_order:
            report = self._module_reports[module_name]
            status = report.headline_status
            clr = status_colors.get(status, CYAN)
            status_text = color(status, clr)
            passed = report.counts.get("PASS", 0)
            failed = report.counts.get("FAIL", 0) + report.counts.get("ERROR", 0)
            skipped = report.counts.get("SKIP", 0)
            duration = _format_duration(report.total_duration)
            module_display = _format_module_display(report.display)
            self.stream.writeln(f"{status_text:<8}{passed:>6}{failed:>6}{skipped:>6}{duration:>10}  {module_display}")

    def _print_outliers(self, limit: int = 3) -> None:
        if not self._all_details:
            return
        sorted_details = sorted(self._all_details, key=lambda d: d.duration)
        fastest = sorted_details[:limit]
        slowest = sorted_details[-limit:][::-1]
        self.stream.writeln("")
        self.stream.writeln(color("Fastest tests:", BRIGHT_GREEN))
        for detail in fastest:
            self._print_outlier_line(detail)
        self.stream.writeln(color("Slowest tests:", BRIGHT_RED))
        for detail in slowest:
            self._print_outlier_line(detail)

    def _print_outlier_line(self, detail: TestDetail) -> None:
        duration = _format_duration(detail.duration)
        location = f"{detail.module or ''}.{detail.cls or ''}".strip(".")
        name = f"{location}::{detail.name}" if location else detail.name
        if not name:
            return
        status_colors = _detail_colors()
        status_text = color(detail.status, status_colors.get(detail.status, CYAN))
        self.stream.writeln(f"  {duration:>8} {status_text:<8} {name}")


def _status_colors() -> dict[str, str]:
    return {"PASS": BRIGHT_GREEN, "FAIL": BRIGHT_RED, "SKIP": BRIGHT_YELLOW}


def _detail_colors() -> dict[str, str]:
    return {
        "PASS": BRIGHT_GREEN,
        "FAIL": BRIGHT_RED,
        "ERROR": BRIGHT_RED,
        "SKIP": BRIGHT_YELLOW,
        "XF": BRIGHT_YELLOW,
        "XPASS": BRIGHT_CYAN,
    }


def _icon_map() -> dict[str, str]:
    return {
        "PASS": color("✓", BRIGHT_GREEN),
        "FAIL": color("✕", BRIGHT_RED),
        "ERROR": color("✕", BRIGHT_RED),
        "SKIP": color("↷", BRIGHT_YELLOW),
        "XF": color("≒", BRIGHT_YELLOW),
        "XPASS": color("★", BRIGHT_CYAN),
    }


def _explicit_label(test: unittest.case.TestCase) -> str:
    # Prefer label set by @test decorator on the bound test method, then on the instance.
    method_name = getattr(test, "_testMethodName", "")
    fn = getattr(test, method_name, None)
    if fn:
        explicit = getattr(fn, "__pyjest_test__", None)
        if explicit:
            return explicit
    explicit = getattr(test, "__pyjest_test__", None)
    if explicit:
        return explicit
    return ""


def _format_badge(status: str, status_colors: dict[str, str]) -> str:
    clr = status_colors.get(status, CYAN)
    if status == "PASS":
        return f"{BG_GREEN}{FG_WHITE}{BOLD} {status} {RESET}"
    if status == "FAIL":
        return f"{BG_RED}{FG_WHITE}{BOLD} {status} {RESET}"
    return color(f" {status} ", clr)


def _format_module_display(display: str) -> str:
    path = Path(display)
    dimmed = str(path.parent) if path.parent != Path(".") else ""
    filename = path.name
    if dimmed:
        return f"{DIM}{dimmed}/{RESET}{color(filename, BOLD)}"
    return color(filename, BOLD)


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


class JestStyleTestRunner(unittest.TextTestRunner):
    resultclass = JestStyleResult

    def __init__(
        self,
        spinner: bool = True,
        report_modules: bool = False,
        report_suite_table: bool = False,
        report_outliers: bool = False,
        progress_fancy: int = 0,
        **kwargs,
    ):
        self.spinner = spinner
        self._report_modules = report_modules
        self._report_suite_table = report_suite_table
        self._report_outliers = report_outliers
        self.progress_fancy = progress_fancy
        super().__init__(verbosity=2, **kwargs)

    def run(self, test):  # type: ignore[override]
        result = self._makeResult()
        result.failfast = self.failfast
        result.buffer = self.buffer
        result.spinner_enabled = self.spinner
        result.report_modules = self._report_modules
        result.report_suite_table = self._report_suite_table
        result.report_outliers = self._report_outliers
        result.progress_fancy_level = getattr(self, "progress_fancy", 0)
        start_time = time.perf_counter()

        result.startTestRun()
        try:
            test(result)
        finally:
            result.stopTestRun()
        result.close_progress_block()

        # Drop a newline after the inline progress symbols.
        if self.stream is not None:
            self.stream.writeln("")
        duration = time.perf_counter() - start_time
        result.print_module_reports()
        result.printErrors()
        self._print_summary(result, duration)
        # Drop a blank line after summary to separate from any prior status line.
        self.stream.writeln("")
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
        print_snapshot_summary()

    def _print_group(self, group: ClassGroup, detail_colors: dict[str, str], icon_map: dict[str, str]) -> None:
        description = group.doc_title or group.name
        class_line = f"  {color('›', BRIGHT_CYAN)} {description}"
        self.stream.writeln(class_line)
        for detail in group.tests:
            self._print_detail(detail, detail_colors, icon_map)

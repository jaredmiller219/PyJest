import importlib
import io
import unittest
from pathlib import Path
from unittest import mock
import contextlib

from pyjest import cli, describe, test

main_module = importlib.import_module("pyjest.main")


def _parse(*argv: str):
    return main_module._prepare_args(list(argv))


@describe("CLI argument parsing")
class CliArgumentParsingTests(unittest.TestCase):
    def _assert_argparse_error(self, *argv: str) -> None:
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(cli.argparse.ArgumentParser, "print_usage", lambda *a, **k: None))
            stack.enter_context(mock.patch.object(cli.argparse.ArgumentParser, "print_help", lambda *a, **k: None))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            with self.assertRaises(SystemExit):
                _parse(*argv)

    @test("applies default values")
    def test_defaults_are_applied(self) -> None:
        args = _parse("tests")

        self.assertFalse(args.watch)
        self.assertEqual(args.watch_interval, 1.0)
        self.assertEqual(args.watch_debounce, 0.2)
        self.assertFalse(args.run_failures_first)
        self.assertFalse(args.onlyChanged)
        self.assertEqual(args.maxTargetsPerWorker, 0)
        self.assertIsNone(args.root)
        self.assertEqual(args.pattern, "test*.py")
        self.assertEqual(args.pattern_exclude, [])
        self.assertEqual(args.ignore, [])
        self.assertFalse(args.failfast)
        self.assertFalse(args.bail)
        self.assertFalse(args.runInBand)
        self.assertEqual(args.maxWorkers, 1)
        self.assertFalse(args.updateSnapshot)
        self.assertFalse(args.snapshot_summary)
        self.assertFalse(args.coverage_bars)
        self.assertEqual(args.progress_fancy, 0)
        self.assertFalse(args.coverage)
        self.assertIsNone(args.coverage_html)
        self.assertIsNone(args.coverage_threshold)
        self.assertEqual(args.report_format, ["console"])
        self.assertTrue(args.report_modules)
        self.assertFalse(args.report_suite_table)
        self.assertFalse(args.report_outliers)
        self.assertEqual(args.max_diff_lines, 200)
        self.assertTrue(args.color_diffs)
        self.assertFalse(args.buffer)
        self.assertEqual(args.targets, ["tests"])
        self.assertFalse(args.pyjest_only)

    # Watch and scheduling -------------------------------------------------

    @test("sets watch flag")
    def test_watch_flag_sets_true(self) -> None:
        args = _parse("--watch")
        self.assertTrue(args.watch)

    @test("parses watch interval and debounce")
    def test_watch_interval_and_debounce_values(self) -> None:
        args = _parse("--watch-interval", "2.5", "--watch-debounce", "0.7")
        self.assertAlmostEqual(args.watch_interval, 2.5)
        self.assertAlmostEqual(args.watch_debounce, 0.7)

    @test("sets run failures first")
    def test_run_failures_first_flag_sets_true(self) -> None:
        args = _parse("--run-failures-first")
        self.assertTrue(args.run_failures_first)

    @test("sets onlyChanged flag")
    def test_only_changed_flag_sets_true(self) -> None:
        args = _parse("--onlyChanged")
        self.assertTrue(args.onlyChanged)

    @test("parses max targets per worker")
    def test_max_targets_per_worker_value(self) -> None:
        args = _parse("--maxTargetsPerWorker", "5")
        self.assertEqual(args.maxTargetsPerWorker, 5)

    @test("maps short aliases correctly")
    def test_short_aliases_map_correctly(self) -> None:
        args = _parse(
            "--w",
            "--wi",
            "1.25",
            "--wd",
            "0.3",
            "--rff",
            "--oc",
            "--mtpw",
            "3",
            "--rt",
            "/tmp/aliases",
            "--p",
            "alias_*.py",
            "--pe",
            "*skip.py",
            "--ig",
            "tmp",
            "--ff",
            "--rib",
            "--mw",
            "1",
            "--us",
            "--ss",
            "--cov",
            "--cov-html",
            "html-out",
            "--cov-thresh",
            "99.9",
            "--rf",
            "json",
            "--nrm",
            "--rst",
            "--ro",
            "--mdl",
            "15",
            "--ncd",
            "--buf",
            "targetA",
            "targetB",
        )

        self.assertTrue(args.watch)
        self.assertAlmostEqual(args.watch_interval, 1.25)
        self.assertAlmostEqual(args.watch_debounce, 0.3)
        self.assertTrue(args.run_failures_first)
        self.assertTrue(args.onlyChanged)
        self.assertEqual(args.maxTargetsPerWorker, 3)
        self.assertEqual(args.root, Path("/tmp/aliases"))
        self.assertEqual(args.pattern, "alias_*.py")
        self.assertEqual(args.pattern_exclude, ["*skip.py"])
        self.assertEqual(args.ignore, ["tmp"])
        self.assertTrue(args.failfast)
        self.assertTrue(args.runInBand)
        self.assertEqual(args.maxWorkers, 1)
        self.assertTrue(args.updateSnapshot)
        self.assertTrue(args.snapshot_summary)
        self.assertTrue(args.coverage)
        self.assertEqual(args.coverage_html, "html-out")
        self.assertAlmostEqual(args.coverage_threshold, 99.9)
        self.assertIn("json", args.report_format)
        self.assertIn("console", args.report_format)
        self.assertFalse(args.report_modules)
        self.assertTrue(args.report_suite_table)
        self.assertTrue(args.report_outliers)
        self.assertEqual(args.max_diff_lines, 15)
        self.assertFalse(args.color_diffs)
        self.assertTrue(args.buffer)
        self.assertEqual(args.targets, ["targetA", "targetB"])

    # Discovery -----------------------------------------------------------

    @test("sets root path")
    def test_root_sets_path(self) -> None:
        args = _parse("--root", "/tmp/project")
        self.assertEqual(args.root, Path("/tmp/project"))

    @test("overrides discovery pattern")
    def test_pattern_override(self) -> None:
        args = _parse("--pattern", "foo_*.py")
        self.assertEqual(args.pattern, "foo_*.py")

    @test("collects multiple pattern excludes")
    def test_pattern_exclude_multiple(self) -> None:
        args = _parse("--pattern-exclude", "*old.py", "--pattern-exclude", "*skip.py")
        self.assertEqual(args.pattern_exclude, ["*old.py", "*skip.py"])

    @test("collects multiple ignore paths")
    def test_ignore_multiple_paths(self) -> None:
        args = _parse("--ignore", "build", "--ignore", "dist")
        self.assertEqual(args.ignore, ["build", "dist"])

    # Execution -----------------------------------------------------------

    @test("sets runInBand flag")
    def test_run_in_band_flag_sets_true(self) -> None:
        args = _parse("--runInBand")
        self.assertTrue(args.runInBand)

    @test("sets failfast flag")
    def test_failfast_flag_sets_failfast(self) -> None:
        args = _parse("--failfast")
        self.assertTrue(args.failfast)

    @test("bail maps to failfast")
    def test_bail_sets_failfast(self) -> None:
        args = _parse("--bail")
        self.assertTrue(args.failfast)

    @test("bail short alias maps to failfast")
    def test_bail_short_alias_sets_failfast(self) -> None:
        args = _parse("--b")
        self.assertTrue(args.failfast)

    @test("rejects invalid worker counts")
    def test_invalid_worker_counts_raise(self) -> None:
        with self.assertRaises(SystemExit):
            _parse("--maxWorkers", "0")
        with self.assertRaises(SystemExit):
            _parse("--maxTargetsPerWorker", "-1")

    @test("parses positive max workers")
    def test_max_workers_positive_value(self) -> None:
        args = _parse("--maxWorkers", "3")
        self.assertEqual(args.maxWorkers, 3)

    # Snapshots -----------------------------------------------------------

    @test("sets updateSnapshot flag")
    def test_update_snapshot_flag_sets_true(self) -> None:
        args = _parse("--updateSnapshot")
        self.assertTrue(args.updateSnapshot)

    @test("sets snapshot summary flag")
    def test_snapshot_summary_flag_sets_true(self) -> None:
        args = _parse("--snapshot-summary")
        self.assertTrue(args.snapshot_summary)

    # Coverage ------------------------------------------------------------

    @test("coverage html implies coverage on")
    def test_coverage_html_implies_coverage(self) -> None:
        args = _parse("--coverage-html")
        self.assertTrue(args.coverage)
        self.assertEqual(args.coverage_html, "coverage_html")

    @test("coverage short alias enables coverage")
    def test_coverage_short_alias_sets_true(self) -> None:
        args = _parse("--cov")
        self.assertTrue(args.coverage)

    @test("no coverage flag disables coverage even if enabled")
    def test_no_coverage_flag_overrides_enable(self) -> None:
        args = _parse("--coverage", "--no-coverage")
        self.assertFalse(args.coverage)

    @test("parses coverage threshold as float")
    def test_coverage_threshold_parsed_as_float(self) -> None:
        args = _parse("--coverage-threshold", "12.5")
        self.assertTrue(args.coverage)
        self.assertAlmostEqual(args.coverage_threshold, 12.5)

    @test("coverage threshold implies coverage")
    def test_coverage_threshold_implies_coverage(self) -> None:
        args = _parse("--coverage-threshold", "50")
        self.assertTrue(args.coverage)
        self.assertEqual(args.coverage_threshold, 50.0)

    @test("coverage bars flag sets true")
    def test_coverage_bars_flag_sets_true(self) -> None:
        args = _parse("--coverage-bars")
        self.assertTrue(args.coverage_bars)

    # Reporting -----------------------------------------------------------

    @test("report format appends console when missing")
    def test_report_formats_append_console_when_missing(self) -> None:
        args = _parse("--report-format", "json")
        self.assertIn("console", args.report_format)
        self.assertIn("json", args.report_format)

    @test("console not duplicated in report formats")
    def test_console_not_duplicated_in_report_formats(self) -> None:
        args = _parse("--report-format", "console", "json", "tap")
        self.assertEqual(args.report_format.count("console"), 1)
        self.assertIn("json", args.report_format)
        self.assertIn("tap", args.report_format)

    @test("report modules flag true")
    def test_report_modules_flag_true(self) -> None:
        args = _parse("--report-modules")
        self.assertTrue(args.report_modules)

    @test("no report modules flag false")
    def test_no_report_modules_flag_false(self) -> None:
        args = _parse("--no-report-modules")
        self.assertFalse(args.report_modules)

    @test("report suite table flag true")
    def test_report_suite_table_flag_true(self) -> None:
        args = _parse("--report-suite-table")
        self.assertTrue(args.report_suite_table)

    @test("report outliers flag true")
    def test_report_outliers_flag_true(self) -> None:
        args = _parse("--report-outliers")
        self.assertTrue(args.report_outliers)

    @test("progress fancy numeric level")
    def test_progress_fancy_numeric_level(self) -> None:
        args = _parse("--progress-fancy", "1")
        self.assertEqual(args.progress_fancy, 1)

    @test("progress fancy short alias")
    def test_progress_fancy_short_alias(self) -> None:
        args = _parse("--pf", "2")
        self.assertEqual(args.progress_fancy, 2)

    @test("fancy progress alias default flags")
    def test_fancy_progress_alias_and_default_flags(self) -> None:
        args = _parse("--fancy-progress")
        self.assertEqual(args.progress_fancy, 2)
        self.assertTrue(args.report_modules)
        self.assertTrue(args.color_diffs)
        self.assertFalse(args.coverage)
        self.assertIn("console", args.report_format)

    @test("invalid progress fancy level errors")
    def test_progress_fancy_invalid_level_errors(self) -> None:
        self._assert_argparse_error("--progress-fancy", "3")

    # Diff and output -----------------------------------------------------

    @test("no color diffs flag false")
    def test_no_color_diffs_flag_false(self) -> None:
        args = _parse("--no-color-diffs")
        self.assertFalse(args.color_diffs)

    @test("max diff lines value parsed")
    def test_max_diff_lines_value(self) -> None:
        args = _parse("--max-diff-lines", "42")
        self.assertEqual(args.max_diff_lines, 42)

    @test("max diff lines zero allowed")
    def test_max_diff_lines_zero_allowed(self) -> None:
        args = _parse("--max-diff-lines", "0")
        self.assertEqual(args.max_diff_lines, 0)

    @test("buffer flag sets true")
    def test_buffer_flag_sets_true(self) -> None:
        args = _parse("--buffer")
        self.assertTrue(args.buffer)

    @test("pyjest only flag sets true")
    def test_pyjest_only_flag_sets_true(self) -> None:
        args = _parse("--pyjest-only")
        self.assertTrue(args.pyjest_only)

    # Validation ----------------------------------------------------------

    @test("invalid report format choice errors")
    def test_report_format_invalid_choice_errors(self) -> None:
        self._assert_argparse_error("--report-format", "csv")

    # Comprehensive combo -------------------------------------------------

    @test("parses all flags end-to-end")
    def test_parses_all_flags_and_applies_postprocessing(self) -> None:
        args = main_module._prepare_args(
            [
                "--watch",
                "--watch-interval",
                "1.5",
                "--watch-debounce",
                "0.4",
                "--run-failures-first",
                "--onlyChanged",
                "--maxTargetsPerWorker",
                "2",
                "--root",
                "/tmp/pyjest-root",
                "--pattern",
                "custom_*.py",
                "--pattern-exclude",
                "*skip.py",
                "--pattern-exclude",
                "*old.py",
                "--ignore",
                "build",
                "--ignore",
                "dist",
                "--bail",
                "--runInBand",
                "--maxWorkers",
                "2",
                "--updateSnapshot",
                "--snapshot-summary",
                "--coverage-bars",
                "--progress-fancy",
                "2",
                "--coverage",
                "--coverage-html",
                "html_dir",
                "--coverage-threshold",
                "75.5",
                "--report-format",
                "json",
                "tap",
                "--no-report-modules",
                "--report-suite-table",
                "--report-outliers",
                "--max-diff-lines",
                "123",
                "--no-color-diffs",
                "--buffer",
                "tests/fixtures/basic",
            ]
        )

        self.assertTrue(args.watch)
        self.assertEqual(args.watch_interval, 1.5)
        self.assertEqual(args.watch_debounce, 0.4)
        self.assertTrue(args.run_failures_first)
        self.assertTrue(args.onlyChanged)
        self.assertEqual(args.maxTargetsPerWorker, 2)
        self.assertEqual(args.root, Path("/tmp/pyjest-root"))
        self.assertEqual(args.pattern, "custom_*.py")
        self.assertEqual(args.pattern_exclude, ["*skip.py", "*old.py"])
        self.assertEqual(args.ignore, ["build", "dist"])
        self.assertTrue(args.failfast)  # set by --bail
        self.assertTrue(args.runInBand)
        self.assertEqual(args.maxWorkers, 2)
        self.assertTrue(args.updateSnapshot)
        self.assertTrue(args.snapshot_summary)
        self.assertTrue(args.coverage_bars)
        self.assertEqual(args.progress_fancy, 2)
        self.assertTrue(args.coverage)
        self.assertEqual(args.coverage_html, "html_dir")
        self.assertEqual(args.coverage_threshold, 75.5)
        self.assertIn("console", args.report_format)
        self.assertIn("json", args.report_format)
        self.assertIn("tap", args.report_format)
        self.assertFalse(args.report_modules)
        self.assertTrue(args.report_suite_table)
        self.assertTrue(args.report_outliers)
        self.assertEqual(args.max_diff_lines, 123)
        self.assertFalse(args.color_diffs)
        self.assertTrue(args.buffer)
        self.assertEqual(args.targets, ["tests/fixtures/basic"])


if __name__ == "__main__":
    unittest.main()

import importlib
import unittest
from pathlib import Path

from pyjest import cli

main_module = importlib.import_module("pyjest.main")


class CliArgumentParsingTests(unittest.TestCase):
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
        # console is always appended if not present
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

    def test_fancy_progress_alias_and_default_flags(self) -> None:
        args = main_module._prepare_args(["--fancy-progress"])
        self.assertEqual(args.progress_fancy, 2)
        self.assertTrue(args.report_modules)
        self.assertTrue(args.color_diffs)
        self.assertFalse(args.coverage)
        self.assertIn("console", args.report_format)

    def test_invalid_worker_counts_raise(self) -> None:
        with self.assertRaises(SystemExit):
            main_module._prepare_args(["--maxWorkers", "0"])
        with self.assertRaises(SystemExit):
            main_module._prepare_args(["--maxTargetsPerWorker", "-1"])

    def test_coverage_html_implies_coverage(self) -> None:
        args = main_module._prepare_args(["--coverage-html"])
        self.assertTrue(args.coverage)
        self.assertEqual(args.coverage_html, "coverage_html")


if __name__ == "__main__":
    unittest.main()

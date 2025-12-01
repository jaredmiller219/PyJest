import importlib
import unittest
from pathlib import Path

from pyjest import cli

main_module = importlib.import_module("pyjest.main")


class CliArgumentParsingTests(unittest.TestCase):
    def test_defaults_are_applied(self) -> None:
        args = main_module._prepare_args(["tests"])

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

    def test_short_aliases_map_correctly(self) -> None:
        args = main_module._prepare_args(
            [
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
            ]
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


if __name__ == "__main__":
    unittest.main()

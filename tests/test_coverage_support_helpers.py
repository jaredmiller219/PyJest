import builtins
import os
import sys
import unittest
from unittest import mock

from pyjest import describe, test
from pyjest.colors import BRIGHT_GREEN, BRIGHT_RED, BRIGHT_YELLOW
from pyjest import coverage_support


@describe("Coverage helper utilities")
class CoverageSupportTests(unittest.TestCase):
    @test("coverage threshold emits message when failing")
    def test_coverage_threshold_failed_message(self) -> None:
        with mock.patch("sys.stdout", new_callable=mock.MagicMock()) as fake_stdout:
            self.assertFalse(coverage_support.coverage_threshold_failed(None, 50))
            self.assertFalse(coverage_support.coverage_threshold_failed(80, None))
            self.assertTrue(coverage_support.coverage_threshold_failed(50.0, 75.0))

        # Ensure the failure message was printed once for the failing case.
        writes = "".join(call.args[0] for call in fake_stdout.write.mock_calls if call.args)
        self.assertIn("Coverage threshold not met", writes)

    @test("rendered bars honor thresholds and widths")
    def test_render_bar_colors_and_width(self) -> None:
        bar_green = coverage_support._render_bar(95.0, width=10)
        bar_yellow = coverage_support._render_bar(75.0, width=10)
        bar_red = coverage_support._render_bar(10.0, width=8)

        self.assertIn(BRIGHT_GREEN, bar_green)
        self.assertIn("█████████░", bar_green)
        self.assertIn(BRIGHT_YELLOW, bar_yellow)
        self.assertIn("███████░░░", bar_yellow)
        self.assertIn(BRIGHT_RED, bar_red)
        self.assertIn("░░░░░░░░", bar_red)

    @test("retry without C extension falls back cleanly")
    def test_retry_without_c_extension_uses_pure_python(self) -> None:
        sentinel = object()
        prev_coverage = sys.modules.get("coverage")
        prev_tracer = sys.modules.get("coverage.tracer")
        core_env = os.environ.get("COVERAGE_CORE")
        sys.modules["coverage"] = mock.MagicMock()
        sys.modules["coverage.tracer"] = mock.MagicMock()

        def fake_import_module(name, *args, **kwargs):
            if name == "coverage":
                return sentinel
            raise ImportError(name)

        with mock.patch.object(coverage_support.importlib, "import_module", side_effect=fake_import_module) as imp:
            original_import = builtins.__import__
            result = coverage_support._retry_without_c_extension(Exception("coverage.tracer failed"))
            self.assertIs(result, sentinel)
            self.assertIs(builtins.__import__, original_import)
            self.assertEqual(os.environ.get("COVERAGE_CORE"), "pytrace")
            imp.assert_called_with("coverage")

        # Restore sys.modules entries to avoid side effects on other tests.
        if prev_coverage is not None:
            sys.modules["coverage"] = prev_coverage
        else:
            sys.modules.pop("coverage", None)
        if prev_tracer is not None:
            sys.modules["coverage.tracer"] = prev_tracer
        else:
            sys.modules.pop("coverage.tracer", None)
        if core_env is None:
            os.environ.pop("COVERAGE_CORE", None)
        else:
            os.environ["COVERAGE_CORE"] = core_env


if __name__ == "__main__":
    unittest.main()

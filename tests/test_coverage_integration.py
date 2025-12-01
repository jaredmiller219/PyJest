import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pyjest import coverage_support, describe, test
from test_pyjest_cli import _run_pyjest


def _coverage_available() -> bool:
    try:
        # Try constructing a Coverage instance using PyJest's guarded importer.
        coverage_support.make_coverage(Path.cwd())
        return True
    except SystemExit:
        return False


HAS_COVERAGE = _coverage_available()


@unittest.skipUnless(HAS_COVERAGE, "coverage.py not installed")
@describe("Coverage CLI integration")
class CoverageCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        coverage_file = Path(self._tmpdir.name) / ".coverage_tmp"
        self._env_patcher = mock.patch.dict(os.environ, {"COVERAGE_FILE": str(coverage_file)})
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

    @test("coverage threshold passes when target is easily met")
    def test_coverage_threshold_passes(self) -> None:
        result = _run_pyjest(
            ["--pattern", "fixture_*.py", "tests/fixtures/basic", "--coverage", "--coverage-threshold", "0"]
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("TOTAL", result.stdout)

    @test("coverage threshold fails when target is impossible")
    def test_coverage_threshold_fails(self) -> None:
        result = _run_pyjest(
            [
                "--pattern",
                "fixture_*.py",
                "tests/fixtures/basic",
                "--coverage",
                "--coverage-threshold",
                "101",
            ]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Coverage threshold not met", result.stdout)

    @test("coverage html report writes and stays in a temp directory")
    def test_coverage_html_report_writes_to_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.dict(
            os.environ,
            {
                # keep all coverage artifacts inside the temp directory
                "COVERAGE_FILE": str(Path(tmpdir) / ".coverage_tmp"),
                "COVERAGE_HTML_DIR": tmpdir,
            },
        ):
            args = [
                "--pattern",
                "fixture_*.py",
                "tests/fixtures/basic",
                "--coverage",
                "--coverage-html",
                tmpdir,
            ]
            result = _run_pyjest(args)
            self.assertEqual(result.returncode, 0, msg=result.stdout)
            self.assertIn("HTML coverage report written", result.stdout)
            self.assertTrue((Path(tmpdir) / "index.html").exists())


if __name__ == "__main__":
    unittest.main()

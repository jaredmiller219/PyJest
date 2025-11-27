import unittest

from test_pyjest_cli import _run_pyjest

try:
    import coverage  # type: ignore  # noqa: F401

    HAS_COVERAGE = True
except Exception:  # pragma: no cover
    HAS_COVERAGE = False


@unittest.skipUnless(HAS_COVERAGE, "coverage.py not installed")
class CoverageCLITests(unittest.TestCase):
    def test_coverage_threshold_passes(self) -> None:
        result = _run_pyjest(
            ["--pattern", "fixture_*.py", "tests/fixtures/basic", "--coverage", "--coverage-threshold", "0"]
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("TOTAL", result.stdout)

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


if __name__ == "__main__":
    unittest.main()

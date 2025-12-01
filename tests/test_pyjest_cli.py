import os
import subprocess
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def _run_pyjest(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    cmd = [sys.executable, "-m", "pyjest"] + args
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


class PyjestCliTests(unittest.TestCase):
    def test_cli_passes_on_clean_suite(self) -> None:
        result = _run_pyjest(["--pattern", "fixture_*.py", "tests/fixtures/basic"])
        self.assertEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("Test Suites", result.stdout)

    def test_cli_reports_failure_exit(self) -> None:
        result = _run_pyjest(["--pattern", "fixture_*.py", "tests/fixtures/failing"])
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("FAIL", result.stdout)

    def test_cli_rejects_missing_root(self) -> None:
        missing_root = PROJECT_ROOT / "missing_pyjest_root_dir"
        self.assertFalse(missing_root.exists(), "Test assumes the missing root does not exist")

        result = _run_pyjest(["--root", str(missing_root)])
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("--root path not found", result.stdout)


if __name__ == "__main__":
    unittest.main()

import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from pyjest import describe, test
from pyjest.reporter import JestStyleResult, ModuleReport, TestDetail
from pyjest import reporting


@describe("Machine-readable report emitters")
class ReportingOutputTests(unittest.TestCase):
    @test("writes JSON, TAP, and JUnit reports with suffix sanitization")
    def test_emit_reports_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = JestStyleResult(stream=io.StringIO(), descriptions=False, verbosity=1)
            module = ModuleReport(key="pkg.test_mod", display="pkg.test_mod", doc_title=None)
            module.register(
                "Suite",
                None,
                TestDetail(
                    name="test fails",
                    status="FAIL",
                    duration=0.1,
                    detail="boom",
                    module="pkg.test_mod",
                    cls="Suite",
                ),
            )
            result._module_reports = {module.key: module}
            result._module_order = [module.key]
            result.testsRun = 1
            result.failures = [("x", "y")]
            result.errors = []
            result.skipped = []
            result._successes = []

            args = SimpleNamespace(report_format=["json", "tap", "junit", "console"], root=tmpdir, report_suffix="worker/1")
            reporting.emit_reports(result, coverage_percent=12.3, duration=0.25, args=args)

            json_path = Path(tmpdir) / "pyjest-report-worker_1.json"
            tap_path = Path(tmpdir) / "pyjest-report-worker_1.tap"
            junit_path = Path(tmpdir) / "pyjest-report-worker_1.junit.xml"

            self.assertTrue(json_path.exists(), "JSON report missing")
            self.assertTrue(tap_path.exists(), "TAP report missing")
            self.assertTrue(junit_path.exists(), "JUnit report missing")

            payload = json.loads(json_path.read_text())
            self.assertEqual(payload["summary"]["testsRun"], 1)
            self.assertEqual(payload["suites"][0]["tests"][0]["status"], "FAIL")
            self.assertEqual(payload["suites"][0]["tests"][0]["detail"], "boom")

            tap_lines = tap_path.read_text().splitlines()
            self.assertEqual(tap_lines[0], "1..1")
            self.assertIn("not ok 1 - test fails", tap_lines[1])

            tree = ET.parse(junit_path)
            failure = tree.find(".//failure")
            self.assertIsNotNone(failure)
            self.assertIn("boom", failure.text or "")


if __name__ == "__main__":
    unittest.main()

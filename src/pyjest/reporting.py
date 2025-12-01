"""Machine-readable report emitters (JSON, TAP, JUnit)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .reporter import JestStyleResult


def emit_reports(result: JestStyleResult, coverage_percent: float | None, duration: float, args) -> None:
    formats = set(args.report_format or [])
    formats.discard("console")  # console is always shown interactively
    if not formats:
        return
    base_dir = Path(args.root or ".").resolve()
    suffix = getattr(args, "report_suffix", None)
    payload = _build_payload(result, coverage_percent, duration)
    if "json" in formats:
        _write_json_report(base_dir, payload, suffix)
    if "tap" in formats:
        _write_tap_report(base_dir, payload, suffix)
    if "junit" in formats:
        _write_junit_report(base_dir, payload, suffix)


def _build_payload(result: JestStyleResult, coverage_percent: float | None, duration: float) -> dict[str, Any]:
    suites: list[dict[str, Any]] = []
    for module_name in result._module_order:
        report = result._module_reports[module_name]
        suite_entry = {
            "name": report.display,
            "status": report.headline_status,
            "duration": report.total_duration,
            "tests": [],
        }
        for class_name in report.group_order:
            group = report.groups[class_name]
            for test in group.tests:
                suite_entry["tests"].append(
                    {
                        "name": test.name,
                        "status": test.status,
                        "duration": test.duration,
                        "summary": test.summary,
                        "note": test.note,
                        "detail": test.detail,
                        "module": test.module,
                        "class": test.cls,
                    }
                )
        suites.append(suite_entry)
    return {
        "summary": {
            "testsRun": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "successes": len(getattr(result, "successes", [])),
            "duration": duration,
            "coverage": coverage_percent,
        },
        "suites": suites,
    }


def _write_json_report(base_dir: Path, payload: dict[str, Any], suffix: str | None) -> None:
    path = base_dir / f"pyjest-report{_suffix_part(suffix)}.json"
    path.write_text(json.dumps(payload, indent=2))


def _write_tap_report(base_dir: Path, payload: dict[str, Any], suffix: str | None) -> None:
    tests = [t for suite in payload["suites"] for t in suite["tests"]]
    lines = [f"1..{len(tests)}"]
    for idx, test in enumerate(tests, start=1):
        status = "ok" if test["status"] in {"PASS", "XPASS", "XF"} else "not ok"
        name = test["name"]
        lines.append(f"{status} {idx} - {name}")
    (base_dir / f"pyjest-report{_suffix_part(suffix)}.tap").write_text("\n".join(lines))


def _write_junit_report(base_dir: Path, payload: dict[str, Any], suffix: str | None) -> None:
    testsuites = ET.Element("testsuites")
    for suite in payload["suites"]:
        ts = ET.SubElement(
            testsuites,
            "testsuite",
            {
                "name": suite["name"],
                "tests": str(len(suite["tests"])),
                "failures": str(sum(1 for t in suite["tests"] if t["status"] == "FAIL")),
                "errors": str(sum(1 for t in suite["tests"] if t["status"] == "ERROR")),
                "skipped": str(sum(1 for t in suite["tests"] if t["status"] == "SKIP")),
                "time": f"{suite['duration']:.3f}",
            },
        )
        for test in suite["tests"]:
            case = ET.SubElement(
                ts,
                "testcase",
                {
                    "name": test["name"],
                    "classname": test.get("class") or "",
                    "time": f"{test['duration']:.3f}",
                },
            )
            if test["status"] in {"FAIL", "ERROR"} and test["detail"]:
                tag = "failure" if test["status"] == "FAIL" else "error"
                failure = ET.SubElement(case, tag)
                failure.text = test["detail"]
            if test["status"] == "SKIP":
                skipped = ET.SubElement(case, "skipped")
                if test["note"]:
                    skipped.text = test["note"]
    tree = ET.ElementTree(testsuites)
    path = base_dir / f"pyjest-report{_suffix_part(suffix)}.junit.xml"
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _suffix_part(suffix: str | None) -> str:
    if not suffix:
        return ""
    cleaned = suffix.replace("/", "_").replace(" ", "_")
    return f"-{cleaned}"

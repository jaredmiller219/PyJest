"""Test discovery utilities and project context management."""

from __future__ import annotations

import fnmatch
import importlib.util
from importlib.machinery import SourceFileLoader
import inspect
import os
import sys
import unittest
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path.cwd()


def _set_project_root(root: Path) -> None:
    """Record and expose the working tree that contains the tests under run."""
    global PROJECT_ROOT
    PROJECT_ROOT = root.resolve()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


_set_project_root(PROJECT_ROOT)


_MARKED_MODULES: set[str] = set()


def mark_pyjest(module: str | None = None) -> None:
    """Record that a module expects to run under PyJest."""
    if module is None:
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        module = caller.f_globals.get("__name__", "<unknown>") if caller else "<unknown>"
    _MARKED_MODULES.add(module)


def marked_modules() -> tuple[str, ...]:
    """Return the modules that have explicitly opted into PyJest."""
    return tuple(sorted(_MARKED_MODULES))


def _doc_summary(doc: str | None) -> str | None:
    if not doc:
        return None
    cleaned = inspect.cleandoc(doc).strip()
    if not cleaned:
        return None
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _module_display(module_name: str) -> tuple[str, str | None]:
    module = sys.modules.get(module_name)
    doc_title = _doc_summary(getattr(module, "__doc__", None)) if module else None
    if module and hasattr(module, "__file__") and module.__file__:
        path = Path(module.__file__).resolve()
        try:
            rel = path.relative_to(PROJECT_ROOT)
            return str(rel), doc_title
        except ValueError:
            return str(path), doc_title
    return module_name, doc_title


def _format_test_name(test: unittest.case.TestCase) -> str:
    """Return a dotted identifier suitable for error sections."""
    test_id = test.id()
    parts = test_id.split(".")
    if len(parts) >= 3:
        module = ".".join(parts[:-2])
        cls = parts[-2]
        method = parts[-1]
        return f"{module}.{cls}.{method}"
    return test_id


def _format_test_title(test: unittest.case.TestCase) -> str:
    description = test.shortDescription()
    if description:
        return description.strip()
    raw = getattr(test, "_testMethodName", test.id())
    return raw.replace("_", " ").strip()


def _pyjest_matches_pattern(path: Path, pattern: str) -> bool:
    """Return True if a .pyjest file logically matches the discovery pattern."""
    pretend_py = path.with_suffix(".py").name
    return fnmatch.fnmatch(pretend_py, pattern)


def _load_tests_from_pyjest_file(loader: unittest.TestLoader, path: Path) -> unittest.TestSuite:
    module_name = _module_name_from_path(path)
    loader_obj = SourceFileLoader(module_name, str(path))
    spec = importlib.util.spec_from_loader(module_name, loader_obj)
    if spec is None:
        raise ImportError(f"Cannot import PyJest test module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader_obj.exec_module(module)
    return loader.loadTestsFromModule(module)


def _discover_pyjest_files(loader: unittest.TestLoader, directory: Path, pattern: str) -> list[unittest.TestSuite]:
    suites: list[unittest.TestSuite] = []
    for file in sorted(directory.rglob("*.pyjest")):
        if not _pyjest_matches_pattern(file, pattern):
            continue
        suites.append(_load_tests_from_pyjest_file(loader, file))
    return suites


def _load_directory_suite(loader: unittest.TestLoader, directory: Path, pattern: str) -> unittest.TestSuite:
    base_suite = loader.discover(str(directory), pattern=pattern)
    extra = _discover_pyjest_files(loader, directory, pattern)
    if not extra:
        return base_suite
    suites: list[unittest.TestSuite] = [base_suite]
    suites.extend(extra)
    return unittest.TestSuite(suites)


def _is_python_project(root: Path) -> bool:
    markers = ["pyproject.toml", "setup.cfg", "setup.py", "requirements.txt"]
    if any((root / marker).exists() for marker in markers):
        return True
    return any(root.glob("*.py"))


def _ensure_python_project(root: Path) -> None:
    if not _is_python_project(root):
        raise SystemExit(
            "This directory is not a Python/PyJest project.\n"
            "Run pyjest from a project root with a pyproject and .py/.pyjest tests,\n"
            "or pass --root to point at one."
        )


def _module_name_from_path(path: Path) -> str:
    rel = path.resolve()
    try:
        rel = rel.relative_to(PROJECT_ROOT)
    except ValueError:
        return path.stem
    module = ".".join(rel.with_suffix("").parts)
    return module


def _load_targets(loader: unittest.TestLoader, targets: Sequence[str], pattern: str) -> unittest.TestSuite:
    if not targets:
        tests_dir = Path("tests")
        if tests_dir.exists():
            return _load_directory_suite(loader, tests_dir, pattern)
        raise SystemExit("no pyjest file(s) exists")

    suites: list[unittest.TestSuite] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            if not any(path.rglob("*.py")) and not any(path.rglob("*.pyjest")):
                raise SystemExit(
                    f"pyjest only runs Python tests. Directory '{path}' has no .py or .pyjest files."
                )
            suites.append(_load_directory_suite(loader, path, pattern))
            continue
        if path.is_file():
            if path.suffix not in {".py", ".pyjest"}:
                raise SystemExit(f"pyjest can only run Python files: '{path}'")
            if path.suffix == ".pyjest":
                suites.append(_load_tests_from_pyjest_file(loader, path))
                continue
            if path.suffix == ".py":
                raise SystemExit(
                    f"'{path}' is not a .pyjest file. Rename it to end with .pyjest or pass an importable module path."
                )
        suites.append(loader.loadTestsFromName(target))
    return unittest.TestSuite(suites)

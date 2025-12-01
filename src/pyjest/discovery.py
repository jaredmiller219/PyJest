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
from typing import Iterable, Sequence


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


def _auto_patterns(pattern: str, root: Path) -> list[str]:
    """Expand default pattern to include pytest/Django variants if present."""
    patterns = [pattern]
    if pattern == "test*.py":
        if any(root.rglob("*_test.py")):
            patterns.append("*_test.py")
        if (root / "manage.py").exists() or any(root.rglob("tests.py")):
            patterns.append("tests.py")
    # Deduplicate while preserving order
    seen = set()
    unique: list[str] = []
    for pat in patterns:
        if pat in seen:
            continue
        seen.add(pat)
        unique.append(pat)
    return unique


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
    for root, _, files in os.walk(directory):
        for name in files:
            if not name.endswith(".pyjest"):
                continue
            path = Path(root) / name
            if not _pyjest_matches_pattern(path, pattern):
                continue
            suites.append(_load_tests_from_pyjest_file(loader, path))
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


def _load_targets(
    loader: unittest.TestLoader,
    targets: Sequence[str],
    pattern: str,
    pattern_exclude: Sequence[str] | None = None,
    ignores: Sequence[str] | None = None,
) -> unittest.TestSuite:
    targets = _default_targets_if_empty(targets)
    patterns = _auto_patterns(pattern, PROJECT_ROOT)
    exclude_patterns = tuple(pattern_exclude or ())
    ignore_paths = tuple((PROJECT_ROOT / Path(p)).resolve() for p in (ignores or ()))
    suites: list[unittest.TestSuite] = []
    for target in targets:
        suite = _load_single_target(loader, target, patterns)
        suite = _filter_suite(suite, exclude_patterns, ignore_paths)
        suites.append(suite)
    return unittest.TestSuite(suites)


def _has_test_files(path: Path) -> bool:
    for root, _, files in os.walk(path):
        for name in files:
            if name.endswith(".py") or name.endswith(".pyjest"):
                return True
    return False


def _default_targets_if_empty(targets: Sequence[str]) -> Sequence[str]:
    if targets:
        return targets
    tests_dir = Path("tests")
    if tests_dir.exists():
        return (str(tests_dir),)
    raise SystemExit("no pyjest file(s) exists")


def _load_single_target(loader: unittest.TestLoader, target: str, patterns: Sequence[str]) -> unittest.TestSuite:
    path = Path(target)
    if path.is_dir():
        return _load_directory_target(loader, path, patterns)
    if path.is_file():
        return _load_file_target(loader, path)
    return loader.loadTestsFromName(target)


def _load_directory_target(loader: unittest.TestLoader, path: Path, patterns: Sequence[str]) -> unittest.TestSuite:
    if not _has_test_files(path):
        raise SystemExit(f"pyjest only runs Python tests. Directory '{path}' has no .py or .pyjest files.")
    suites = [_load_directory_suite(loader, path, pattern) for pattern in patterns]
    return _merge_suites(suites)


def _load_file_target(loader: unittest.TestLoader, path: Path) -> unittest.TestSuite:
    if path.suffix not in {".py", ".pyjest"}:
        raise SystemExit(f"pyjest can only run Python files: '{path}'")
    if path.suffix == ".pyjest":
        return _load_tests_from_pyjest_file(loader, path)
    raise SystemExit(
        f"'{path}' is not a .pyjest file. Rename it to end with .pyjest or pass an importable module path."
    )


def _merge_suites(suites: Sequence[unittest.TestSuite]) -> unittest.TestSuite:
    tests: list[unittest.case.TestCase] = []
    seen_ids: set[str] = set()
    for suite in suites:
        for test in _iter_tests(suite):
            tid = test.id()
            if tid in seen_ids:
                continue
            seen_ids.add(tid)
            tests.append(test)
    return unittest.TestSuite(tests)


def _iter_tests(suite: unittest.TestSuite) -> Iterable[unittest.case.TestCase]:
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _iter_tests(test)
        else:
            yield test


def _filter_suite(
    suite: unittest.TestSuite, excludes: Sequence[str], ignores: Sequence[Path]
) -> unittest.TestSuite:
    if not excludes and not ignores:
        return suite
    filtered: list[unittest.case.TestCase] = []
    for test in _iter_tests(suite):
        path = _test_file(test)
        if path is None:
            filtered.append(test)
            continue
        if _should_exclude(path, excludes, ignores):
            continue
        filtered.append(test)
    return unittest.TestSuite(filtered)


def _test_file(test: unittest.case.TestCase) -> Path | None:
    module = sys.modules.get(test.__class__.__module__)
    if module and getattr(module, "__file__", None):
        return Path(module.__file__).resolve()
    return None


def _should_exclude(path: Path, excludes: Sequence[str], ignores: Sequence[Path]) -> bool:
    rel = None
    try:
        rel = path.relative_to(PROJECT_ROOT)
    except ValueError:
        rel = path
    rel_str = str(rel)
    if any(rel_str.endswith(pattern) or fnmatch.fnmatch(rel_str, pattern) for pattern in excludes):
        return True
    for ignore in ignores:
        try:
            rel_ignore = rel if rel else path
            if rel_ignore.is_relative_to(ignore):
                return True
        except AttributeError:
            # Python < 3.9 compatibility fallback
            if str(rel_ignore).startswith(str(ignore)):
                return True
    return False

"""Change-to-target mapping heuristics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .discovery import _module_name_from_path


def _import_graph_from_modules(modules: Iterable[str]) -> Mapping[str, set[str]]:
    """Return a shallow import graph mapping module -> direct imports."""
    graph: dict[str, set[str]] = {}
    for name in modules:
        module = sys.modules.get(name)
        if not module or not getattr(module, "__file__", None):
            continue
        deps: set[str] = set()
        try:
            with open(module.__file__, "r") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("import "):
                        parts = line.replace("import", "").strip().split(",")
                        for part in parts:
                            dep = part.strip().split(" ")[0]
                            if dep:
                                deps.add(dep.split(".")[0])
                    elif line.startswith("from "):
                        dep = line.split(" ")[1]
                        if dep:
                            deps.add(dep.split(".")[0])
        except OSError:
            continue
        graph[name] = deps
    return graph


def infer_targets_from_changes(changed: set[Path], default_targets: Sequence[str]) -> list[str]:
    """Try to pick targets based on changed files and loaded modules."""
    targets = set()
    for path in changed:
        if path.suffix in {".py", ".pyjest"}:
            targets.add(_module_name_from_path(path))
    # If we saw only non-test files, map to modules that import them (best-effort).
    if not targets:
        graph = _import_graph_from_modules(sys.modules.keys())
        changed_modules = {_module_name_from_path(path) for path in changed}
        for mod, deps in graph.items():
            if any(dep in changed_modules for dep in deps):
                targets.add(mod)
    return list(targets) or list(default_targets)

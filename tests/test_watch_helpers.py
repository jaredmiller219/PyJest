import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace, ModuleType
import unittest
import unittest.mock

from pyjest import describe, test
from pyjest import watch
from pyjest.change_map import infer_targets_from_changes
from pyjest.discovery import PROJECT_ROOT, _set_project_root
from pyjest.orchestrator import watch_loop


@describe("Watch helper utilities")
class WatchHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._prev_root = PROJECT_ROOT
        self._prev_sys_path = list(sys.path)
        _set_project_root(Path(self._tmpdir.name))

    def tearDown(self) -> None:
        _set_project_root(self._prev_root)
        sys.path = self._prev_sys_path

    @test("targets_from_changed maps file types and defaults")
    def test_targets_from_changed(self) -> None:
        root = Path(self._tmpdir.name)
        py_path = root / "pkg" / "module.py"
        py_path.parent.mkdir(parents=True)
        pyjest_path = root / "custom.test.pyjest"
        changed = {pyjest_path, py_path}

        targets = watch.targets_from_changed(changed, ["fallback"])

        self.assertIn(str(pyjest_path), targets)
        self.assertIn("pkg.module", targets)

    @test("targets_from_changed falls back when nothing changed")
    def test_targets_from_changed_defaults_when_empty(self) -> None:
        targets = watch.targets_from_changed(set(), ["default"])
        self.assertEqual(targets, ["default"])

    @test("diff snapshot detects added removed and changed files")
    def test_diff_snapshots(self) -> None:
        prev = {Path("a.py"): 1.0, Path("b.py"): 2.0}
        current = {Path("a.py"): 1.0, Path("c.py"): 3.0}

        changed = watch._diff_snapshots(prev, current)

        self.assertEqual(changed, {Path("b.py"), Path("c.py")})

    @test("next targets prefer onlyChanged and failures when configured")
    def test_next_targets_prefers_flags(self) -> None:
        root = Path(self._tmpdir.name)
        changed = {root / "example.py"}
        args_only_changed = SimpleNamespace(
            onlyChanged=True,
            run_failures_first=False,
            targets=["tests"],
        )
        args_run_failures_first = SimpleNamespace(
            onlyChanged=False,
            run_failures_first=True,
            targets=["tests"],
        )

        only_changed_targets = watch_loop._next_targets(args_only_changed, changed, ["mod.failed"])
        failures_first_targets = watch_loop._next_targets(args_run_failures_first, changed, ["mod.failed"])

        self.assertEqual(only_changed_targets, ["example"])
        self.assertEqual(failures_first_targets, ["mod.failed"])

    @test("next targets falls back to change mapping heuristics")
    def test_next_targets_calls_change_mapper(self) -> None:
        root = Path(self._tmpdir.name)
        changed = {root / "util.py"}
        args = SimpleNamespace(onlyChanged=False, run_failures_first=False, targets=["tests"])

        def fake_infer(changed_paths, default_targets):
            self.assertEqual(changed_paths, changed)
            self.assertEqual(default_targets, ["tests"])
            return ["heuristic.target"]

        with unittest.mock.patch.object(watch_loop, "infer_targets_from_changes", fake_infer):
            targets = watch_loop._next_targets(args, changed, [])

        self.assertEqual(targets, ["heuristic.target"])


@describe("Change-to-target mapping")
class ChangeMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._prev_root = PROJECT_ROOT
        self._prev_sys_path = list(sys.path)
        _set_project_root(Path(self._tmpdir.name))

    def tearDown(self) -> None:
        _set_project_root(self._prev_root)
        sys.path = self._prev_sys_path

    @test("parses common import line shapes")
    def test_parse_import_line_variants(self) -> None:
        from pyjest import change_map

        self.assertEqual(change_map._parse_import_line("import a, b as c"), {"a", "b"})
        self.assertEqual(change_map._parse_import_line("from pkg.sub import thing as alias"), {"pkg"})

    @test("maps non-test changes back to importing modules")
    def test_infer_targets_from_non_test_changes(self) -> None:
        from pyjest import change_map

        root = Path(self._tmpdir.name)
        util_path = root / "pyjest_temp_mod_abc.txt"
        app_path = root / "pyjest_temp_app.py"
        util_path.write_text("VALUE = 1\n")
        app_path.write_text("import pyjest_temp_mod_abc\n")

        app_module = ModuleType("pyjest_temp_app")
        app_module.__file__ = str(app_path)
        sys.modules["pyjest_temp_app"] = app_module
        self.addCleanup(sys.modules.pop, "pyjest_temp_app", None)

        fake_graph = {"pyjest_temp_app": {"pyjest_temp_mod_abc"}}
        with unittest.mock.patch.object(change_map, "_import_graph_from_modules", return_value=fake_graph):
            targets = infer_targets_from_changes({util_path}, default_targets=("fallback",))

        self.assertIn("pyjest_temp_app", targets)
        self.assertNotIn("fallback", targets)

import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from pyjest import describe, test
from pyjest import snapshot


@describe("Snapshot store robustness")
class SnapshotStoreTests(unittest.TestCase):
    @test("handles malformed or non-dict snapshot files")
    def test_read_snapshot_file_resilience(self) -> None:
        store = snapshot.SnapshotStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            broken = Path(tmpdir) / "broken.snap.json"
            broken.write_text("not-json")
            not_dict = Path(tmpdir) / "list.snap.json"
            not_dict.write_text("[]")

            self.assertEqual(store._read_snapshot_file(broken), {})
            self.assertEqual(store._read_snapshot_file(not_dict), {})
            # Missing file returns an empty mapping.
            self.assertEqual(store._read_snapshot_file(Path(tmpdir) / "missing.snap.json"), {})

    @test("prints a summary when show_summary is enabled with no changes")
    def test_print_snapshot_summary_when_none_touched(self) -> None:
        original_store = snapshot.STORE
        replacement = snapshot.SnapshotStore()
        replacement.show_summary = True
        snapshot.STORE = replacement
        try:
            buffer = io.StringIO()
            with mock.patch("sys.stdout", buffer):
                snapshot.print_snapshot_summary()
            self.assertIn("Snapshots touched: none", buffer.getvalue())
        finally:
            snapshot.STORE = original_store

    @test("derives default snapshot names and caller fallbacks")
    def test_default_snapshot_naming_and_context(self) -> None:
        module, test_name = snapshot._caller_test_context()
        self.assertEqual(
            test_name,
            "SnapshotStoreTests::test_default_snapshot_naming_and_context",
        )
        self.assertIn(module, {"tests.test_snapshot_store", "test_snapshot_store"})

        # When called outside a unittest.TestCase context, we fall back to unknowns.
        result_holder: list[tuple[str, str]] = []

        def _call_from_thread():
            result_holder.append(snapshot._caller_test_context())

        thread = threading.Thread(target=_call_from_thread)
        thread.start()
        thread.join()
        self.assertIn(result_holder[0][0], {"tests.test_snapshot_store", "test_snapshot_store"})
        self.assertEqual(result_holder[0][1], "NoneType::_call_from_thread")

        computed = snapshot._default_snapshot_name("m", "t")
        self.assertEqual(computed, "m::t")


if __name__ == "__main__":
    unittest.main()

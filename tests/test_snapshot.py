import shutil
import tempfile
import unittest
from pathlib import Path

from pyjest import describe, test
from pyjest.assertions import expect
from pyjest.snapshot import STORE as SNAPSHOTS


@describe("Snapshot assertions")
class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = Path(tempfile.mkdtemp(prefix="pyjest_snap_"))
        self.prev_root = SNAPSHOTS.root
        self.prev_update = SNAPSHOTS.update
        SNAPSHOTS.configure(root=self.tempdir, update=True)

    def tearDown(self) -> None:
        SNAPSHOTS.configure(root=self.prev_root, update=self.prev_update)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    @test("creates and matches snapshot")
    def test_creates_and_matches_snapshot(self) -> None:
        value = {"answer": 42}
        expect(value).to_match_snapshot()
        # Second call should read the stored snapshot and pass
        expect(value).to_match_snapshot()

    @test("missing snapshot requires update flag")
    def test_missing_snapshot_requires_update_flag(self) -> None:
        SNAPSHOTS.configure(root=self.tempdir, update=False)
        with self.assertRaises(AssertionError):
            expect({"a": 1}).to_match_snapshot("custom")


if __name__ == "__main__":
    unittest.main()

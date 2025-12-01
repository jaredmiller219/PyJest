import unittest

from pyjest import describe, test

from test_pyjest_cli import _run_pyjest


@describe("Parallel CLI")
class ParallelCLITests(unittest.TestCase):
    @test("parallel targets run")
    def test_parallel_targets(self) -> None:
        result = _run_pyjest(
            [
                "--pattern",
                "fixture_*.py",
                "tests/fixtures/basic",
                "tests/fixtures/extra",
                "--maxWorkers",
                "2",
            ]
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout)


if __name__ == "__main__":
    unittest.main()

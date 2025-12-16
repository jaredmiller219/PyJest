import io
import unittest

from pyjest import describe, test
from pyjest.reporter import JestStyleTestRunner


@describe("KeyboardInterrupt handling")
class InterruptHandlingTests(unittest.TestCase):
    @test("runner stays quiet after Ctrl-C")
    def test_runner_stays_quiet_after_ctrl_c(self) -> None:
        stream = io.StringIO()
        runner = JestStyleTestRunner(stream=stream, spinner=False)

        class InterruptingCase(unittest.TestCase):
            def test_interrupt(self) -> None:
                raise KeyboardInterrupt()

        suite = unittest.TestLoader().loadTestsFromTestCase(InterruptingCase)

        with self.assertRaises(KeyboardInterrupt):
            runner.run(suite)

        output = stream.getvalue()
        self.assertIn("Test run interrupted by user.", output)
        self.assertNotIn("Test Suites:", output)


if __name__ == "__main__":
    unittest.main()

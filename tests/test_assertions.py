import asyncio
import unittest

from pyjest.assertions import expect, expect_async


class ExpectationTests(unittest.TestCase):
    def test_to_equal_with_diff(self) -> None:
        with self.assertRaises(AssertionError) as ctx:
            expect({"a": 1, "b": 2}).to_equal({"a": 1, "b": 3})
        self.assertIn("Diff:", str(ctx.exception))

    def test_to_be_identity(self) -> None:
        obj = object()
        expect(obj).to_be(obj)
        with self.assertRaises(AssertionError):
            expect(obj).to_be(object())

    def test_truthiness(self) -> None:
        expect("x").to_be_truthy()
        with self.assertRaises(AssertionError):
            expect("").to_be_truthy()
        expect("").to_be_falsy()

    def test_none_and_instance(self) -> None:
        expect(None).to_be_none()
        with self.assertRaises(AssertionError):
            expect("x").to_be_none()
        expect(1).to_be_instance_of(int)
        with self.assertRaises(AssertionError):
            expect(1).to_be_instance_of(str)

    def test_containment_and_length(self) -> None:
        expect([1, 2, 3]).to_contain(2)
        with self.assertRaises(AssertionError):
            expect([1, 2, 3]).to_contain(4)
        expect([1, 2, 3]).to_have_length(3)
        with self.assertRaises(AssertionError):
            expect([1, 2, 3]).to_have_length(2)

    def test_match_and_keys(self) -> None:
        expect("hello world").to_match(r"hello")
        with self.assertRaises(AssertionError):
            expect("hello").to_match(r"world")
        expect({"a": 1, "b": 2}).to_have_keys(["a"])
        with self.assertRaises(AssertionError):
            expect({"a": 1}).to_have_keys(["b"])

    def test_to_raise(self) -> None:
        def boom():
            raise ValueError("nope")

        expect(boom).to_raise(ValueError, "nope")
        with self.assertRaises(AssertionError):
            expect(lambda: None).to_raise(ValueError)

    def test_async_expectation(self) -> None:
        async def add_one(value):
            return value + 1

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(expect_async(add_one(1)).to_resolve_to(2))
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()

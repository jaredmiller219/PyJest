"""Lightweight Jest-style expectation helpers."""

from __future__ import annotations

import asyncio
import difflib
import pprint
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .snapshot import STORE
from .colors import BRIGHT_CYAN, BRIGHT_GREEN, BRIGHT_RED, DIM, RESET, color


@dataclass
class DiffConfig:
    max_lines: int | None = 200
    color: bool = True


DIFF_CONFIG = DiffConfig()


def configure_diffs(max_lines: int | None, color: bool) -> None:
    max_lines = None if max_lines is not None and max_lines <= 0 else max_lines
    DIFF_CONFIG.max_lines = max_lines
    DIFF_CONFIG.color = color


def _pretty(value: Any) -> str:
    return pprint.pformat(value, width=80, compact=True)


def _diff(expected: Any, actual: Any) -> str:
    left, right = _normalize_diff_inputs(expected, actual)
    lines = list(difflib.ndiff(left, right))
    lines = _maybe_truncate(lines)
    if not DIFF_CONFIG.color:
        return "\n".join(lines)
    return "\n".join(_colorize_diff_line(line) for line in lines)


def _normalize_diff_inputs(expected: Any, actual: Any) -> tuple[list[str], list[str]]:
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.splitlines(), actual.splitlines()
    return _pretty(expected).splitlines(), _pretty(actual).splitlines()


def _maybe_truncate(lines: list[str]) -> list[str]:
    max_lines = DIFF_CONFIG.max_lines
    if max_lines is None or len(lines) <= max_lines:
        return lines
    head = lines[: max_lines - 1]
    head.append(f"... ({len(lines) - len(head)} more lines truncated)")
    return head


def _colorize_diff_line(line: str) -> str:
    if line.startswith("+"):
        return color(line, BRIGHT_GREEN)
    if line.startswith("-"):
        return color(line, BRIGHT_RED)
    if line.startswith("?"):
        return color(line, BRIGHT_CYAN)
    return color(line, DIM)


def expect(value: Any) -> "Expectation":
    return Expectation(value)


def expect_async(awaitable) -> "AsyncExpectation":
    return AsyncExpectation(awaitable)


@dataclass
class Expectation:
    value: Any

    def _fail(self, message: str) -> None:
        raise AssertionError(message)

    def to_equal(self, expected: Any) -> None:
        if self.value != expected:
            message = f"Expected values to be equal.\nExpected: {_pretty(expected)}\nReceived: {_pretty(self.value)}"
            message += f"\nDiff:\n{_diff(expected, self.value)}"
            self._fail(message)

    def to_be(self, expected: Any) -> None:
        if self.value is not expected:
            self._fail(f"Expected objects to be identical.\nExpected: {id(expected)}\nReceived: {id(self.value)}")

    def to_be_truthy(self) -> None:
        if not self.value:
            self._fail("Expected value to be truthy, but it was falsy.")

    def to_be_falsy(self) -> None:
        if self.value:
            self._fail("Expected value to be falsy, but it was truthy.")

    def to_be_none(self) -> None:
        if self.value is not None:
            self._fail(f"Expected None, received: {_pretty(self.value)}")

    def to_be_instance_of(self, cls: type) -> None:
        if not isinstance(self.value, cls):
            self._fail(f"Expected instance of {cls.__name__}, received {type(self.value).__name__}")

    def to_contain(self, item: Any) -> None:
        try:
            contains = item in self.value  # type: ignore[operator]
        except Exception as exc:  # pragma: no cover - defensive
            self._fail(f"Could not check containment: {exc}")
            return
        if not contains:
            self._fail(f"Expected {_pretty(self.value)} to contain {_pretty(item)}")

    def to_have_length(self, length: int) -> None:
        try:
            actual_length = len(self.value)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - defensive
            self._fail(f"Could not get length: {exc}")
            return
        if actual_length != length:
            self._fail(f"Expected length {length}, received {actual_length}")

    def to_match(self, pattern: str | re.Pattern[str]) -> None:
        if not isinstance(self.value, str):
            self._fail(f"to_match requires a string value, received {type(self.value).__name__}")
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        if not regex.search(self.value):  # type: ignore[arg-type]
            self._fail(f"Expected string to match {regex.pattern!r}, received {self.value!r}")

    def to_have_keys(self, keys: Iterable[Any]) -> None:
        if not isinstance(self.value, Mapping):
            self._fail(f"to_have_keys requires a mapping, received {type(self.value).__name__}")
        missing = [key for key in keys if key not in self.value]  # type: ignore[operator]
        if missing:
            self._fail(f"Missing keys: {_pretty(missing)} in {_pretty(self.value)}")

    def to_raise(self, exc_type: type[BaseException] = Exception, match: str | None = None) -> None:
        self._assert_callable()
        try:
            self.value()
        except exc_type as exc:
            if match and not re.search(match, str(exc)):
                self._fail(f"Expected exception message to match {match!r}, received {str(exc)!r}")
            return
        except Exception as exc:
            self._fail(f"Expected {exc_type.__name__}, but {type(exc).__name__} was raised")
        else:
            self._fail(f"Expected {exc_type.__name__} to be raised, but no exception occurred")

    def to_match_snapshot(self, name: str | None = None) -> None:
        STORE.assert_match(self.value, name=name)

    def _assert_callable(self) -> None:
        if not callable(self.value):
            self._fail("to_raise requires a callable value")


@dataclass
class AsyncExpectation:
    awaitable: Any

    async def to_resolve_to(self, expected: Any) -> None:
        if not asyncio.iscoroutine(self.awaitable):
            raise AssertionError("to_resolve_to requires an awaitable value")
        actual = await self.awaitable
        Expectation(actual).to_equal(expected)

    async def to_raise(self, exc_type: type[BaseException] = Exception, match: str | None = None) -> None:
        if not asyncio.iscoroutine(self.awaitable):
            raise AssertionError("to_raise requires an awaitable value")
        try:
            await self.awaitable
        except exc_type as exc:
            if match and not re.search(match, str(exc)):
                raise AssertionError(
                    f"Expected exception message to match {match!r}, received {str(exc)!r}"
                ) from exc
            return
        except Exception as exc:
            raise AssertionError(f"Expected {exc_type.__name__}, but {type(exc).__name__} was raised") from exc
        raise AssertionError(f"Expected {exc_type.__name__} to be raised, but no exception occurred")

"""Lightweight helpers to label tests with Jest-style describe/test strings."""

from __future__ import annotations

from typing import Callable, Iterable, TypeVar

F = TypeVar("F", bound=Callable[..., object])
T = TypeVar("T", bound=type)


def _mark_skip(target: object, reason: str) -> None:
    # unittest looks for these attributes to skip tests/classes without wrapping
    setattr(target, "__unittest_skip__", True)
    setattr(target, "__unittest_skip_why__", reason)


class _DescribeDecorator:
    def __call__(self, label: str) -> Callable[[T], T]:
        def decorator(cls: T) -> T:
            setattr(cls, "__pyjest_describe__", label)
            return cls

        return decorator

    def skip(self, label: str, reason: str | None = None) -> Callable[[T], T]:
        skip_reason = reason or label

        def decorator(cls: T) -> T:
            setattr(cls, "__pyjest_describe__", label)
            _mark_skip(cls, skip_reason)
            return cls

        return decorator

    def only(self, label: str) -> Callable[[T], T]:
        def decorator(cls: T) -> T:
            setattr(cls, "__pyjest_describe__", label)
            setattr(cls, "__pyjest_only__", True)
            return cls

        return decorator


class _TestDecorator:
    def __call__(self, label: str) -> Callable[[F], F]:
        def decorator(fn: F) -> F:
            setattr(fn, "__pyjest_test__", label)
            return fn

        return decorator

    def skip(self, label: str, reason: str | None = None) -> Callable[[F], F]:
        skip_reason = reason or label

        def decorator(fn: F) -> F:
            setattr(fn, "__pyjest_test__", label)
            _mark_skip(fn, skip_reason)
            return fn

        return decorator

    def only(self, label: str) -> Callable[[F], F]:
        def decorator(fn: F) -> F:
            setattr(fn, "__pyjest_test__", label)
            setattr(fn, "__pyjest_only__", True)
            return fn

        return decorator

    def todo(self, label: str) -> Callable[[F], F]:
        todo_reason = f"TODO: {label}"

        def decorator(fn: F) -> F:
            setattr(fn, "__pyjest_test__", label)
            setattr(fn, "__pyjest_todo__", True)
            _mark_skip(fn, todo_reason)
            return fn

        return decorator


describe = _DescribeDecorator()
test = _TestDecorator()


def autolabel(
    transform: Callable[[str], str] | None = None,
    *,
    strip_prefix: str | Iterable[str] | None = None,
    title_case: bool = False,
) -> Callable[[T], T]:
    """Decorator to ensure all test_* methods have a display label.

    If a method already has @test, it is left untouched. Otherwise, we assign
    __pyjest_test__ using the provided transform or a default that can strip
    a prefix (e.g., ``test_``), replace ``_`` with spaces, and optionally title-case.
    """

    def default_transform(name: str) -> str:
        working = name
        if strip_prefix:
            prefixes = (strip_prefix,) if isinstance(strip_prefix, str) else tuple(strip_prefix)
            for prefix in prefixes:
                if working.startswith(prefix):
                    working = working[len(prefix) :]
                    break
        working = working.replace("_", " ")
        return working.title() if title_case else working

    def decorator(cls: T) -> T:
        fn_transform = transform or default_transform
        for attr in dir(cls):
            if not attr.startswith("test"):
                continue
            fn = getattr(cls, attr, None)
            if not callable(fn):
                continue
            if getattr(fn, "__pyjest_test__", None):
                continue
            setattr(fn, "__pyjest_test__", fn_transform(attr))
        return cls

    return decorator

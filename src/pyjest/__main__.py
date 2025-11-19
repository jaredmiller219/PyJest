"""Module so `python -m jestunit` works alongside the console script."""

from __future__ import annotations

from . import main


if __name__ == "__main__":
    raise SystemExit(main())

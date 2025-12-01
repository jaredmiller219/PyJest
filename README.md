# pyjest

`pyjest` is a zero-dependency CLI dedicated to Python projects. It refuses to
run unless it detects Python sources/metadata so you do not accidentally point
it at non-Python trees. It runs standard `unittest` suites with
Jest-like output. Drop it into any repo, `pip install --editable .`, and run the
`pyjest` command to see colorful per-test output, structured summaries, and a
nicer overall experience than `python -m unittest`.

## Usage

```bash
pip install --editable /path/to/pyjest
cd /path/to/your/project
pyjest --pattern 'test_*.py' tests
```

Use `--root /path/to/project` to point the runner at a different working tree
without `cd`-ing first. Targets accept modules, packages, or files ending in
`.py` or `.pyjest`; leave them blank to auto-discover tests in `./tests` (PyJest
automatically picks up `.pyjest` files as part of discovery).

Console output shows per-module/class breakdowns by default. Enable more sections
as needed:

- `--report-suite-table`: compact per-suite table with durations
- `--report-outliers`: fastest/slowest tests

### CLI flags to try

- `--watch [--onlyChanged] [--watch-interval 1.0]`: poll for changes and rerun, optionally narrowing to changed files.
- `--bail`/`--failfast`: stop on first failure.
- `--runInBand`: explicit serial execution (default for now).
- `--maxWorkers 1`: parsed for future parallelism; currently must be 1.
- `--updateSnapshot`: accepted for future snapshot support.
- `--coverage [--coverage-html DIR] [--coverage-threshold PCT]`: optional coverage.py integration; write HTML to `coverage_html` by default when flag is present.
- `--coverage-bars`: show per-file coverage bars/sparklines (optional, quiet by default).
- `--maxWorkers N`: basic parallel run across multiple targets (experimental).
- `--watch-debounce SECONDS`: extra debounce delay after change detection (default 0.2s).
- `--run-failures-first`: in watch mode, rerun failing modules before falling back to other targets.
- Progress: default inline ✓/✕/↷ glyphs now begin with a framed “Progress” banner, drop colored count panels with test #, and add mini stacked bars every few tests; add `--buffer` to switch to a live status line with spinner, elapsed time, test index, and pass/fail/skip counts.
- `--report-format console json tap junit`: emit machine-readable reports alongside console output.
- `--report-modules`: print per-module/class breakdowns.
- `--report-suite-table`: print compact per-suite table.
- `--report-outliers`: print fastest/slowest test sections.
- `--pattern-exclude PATTERN` and `--ignore PATH`: skip noisy files during discovery.
- `--max-diff-lines N` / `--no-color-diffs`: control assertion diff verbosity/colour.

### Expect-style assertions

PyJest ships lightweight matchers:

```python
from pyjest.assertions import expect, expect_async

expect({"a": 1, "b": 2}).to_have_keys(["a"])
expect("hello world").to_match(r"hello")
expect(lambda: (_ for _ in ()).throw(ValueError("boom"))).to_raise(ValueError, "boom")

# Async
async def fetch():
    return {"ok": True}

await expect_async(fetch()).to_resolve_to({"ok": True})

# Snapshots (write with --updateSnapshot)
expect({"nested": ["value"]}).to_match_snapshot()
```

### Typing and editor support

- Package ships `py.typed` so type checkers pick up inline annotations.
- VS Code: `.vscode/launch.json` includes run + watch configs that launch `python -m pyjest` against `tests`.

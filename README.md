# pyjest

`pyjest` is a zero-dependency CLI for running `unittest` suites with
Jest-style reporting. It refuses to run unless it detects Python
sources/metadata so you do not accidentally point it at non-Python trees.
Drop it into any repo, `pip install --editable .`, and run the `pyjest`
command to see colorful per-test output, structured summaries, and a nicer
overall experience than `python -m unittest`.

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

### Discovery and targeting

- Patterns: defaults to `test*.py`, but automatically also tries `*_test.py` and `tests.py` when they exist.
- `.pyjest` files: discovered alongside normal Python tests; use `--pyjest-only` to ignore `.py` files.
- Excludes: `--pattern-exclude PATTERN` and `--ignore PATH` skip noisy files during discovery.
- Targets: pass directories, files, or import paths; omit to run `tests/` if present.

### Jest-style labels

Add readable names to suites and tests:

```python
from pyjest import autolabel, describe, test

@autolabel()  # fill in labels for methods not decorated with @test
@describe("User auth flows")
class AuthTests(unittest.TestCase):
    @test("logs users in with valid credentials")
    def test_login_happy_path(self):
        ...

    def test_logout_shows_confirmation(self):
        ...  # labeled automatically as "test logout shows confirmation"
```

`@describe` sets a class label, `@test` sets a method label, and `@autolabel`
fills in the rest without overriding explicit labels.

Console output shows per-module/class breakdowns by default. Enable more sections
as needed:

- `--report-suite-table`: compact per-suite table with durations
- `--report-outliers`: fastest/slowest tests

### CLI flags to try

- `--watch [--onlyChanged] [--watch-interval 1.0]`: poll for changes and rerun, optionally narrowing to changed files.
- `--bail`/`--failfast`: stop on first failure.
- `--runInBand`: explicit serial execution (default for now).
- `--maxWorkers 1`: parsed for future parallelism; currently must be 1. Use `--maxTargetsPerWorker` to bound work assignment once parallel runs are enabled.
- `--root PATH`: run tests as if started from PATH; affects discovery and reporting roots.
- `--pattern GLOB`: customize discovery glob (default `test*.py`); pair with `--pattern-exclude` and `--ignore` to skip files/dirs.
- `--pyjest-only`: limit discovery to `.pyjest` files, skipping regular `.py` tests.
- `--updateSnapshot`: accepted for future snapshot support.
- `--snapshot-summary`: show a snapshot create/update summary after a run (pairs with `--updateSnapshot`).
- `--coverage [--coverage-html DIR] [--coverage-threshold PCT]`: optional coverage.py integration; write HTML to `coverage_html` by default when flag is present.
- `--no-coverage`: explicitly disable coverage collection.
- `--coverage-bars`: show per-file coverage bars/sparklines (optional, quiet by default).
- `--watch-debounce SECONDS`: extra debounce delay after change detection (default 0.2s).
- `--run-failures-first`: in watch mode, rerun failing modules before falling back to other targets.
- `--buffer`/`--buf`: capture stdout/stderr during tests so progress output stays clean.
- Progress: default inline ✓/✕/↷ glyphs render inside a framed “Progress” block with a centered legend; rows include small padding before the right border, `--progress-fancy {0,1,2}` (or `--fancy-progress`) tunes compact vs framed progress, and `--buffer` switches to a live status line with spinner, elapsed time, test index, and pass/fail/skip counts.
- `--report-format console json tap junit`: emit machine-readable reports alongside console output.
- `--report-modules`/`--no-report-modules`: toggle per-module/class breakdowns.
- `--report-suite-table`: print compact per-suite table.
- `--report-outliers`: print fastest/slowest test sections.
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

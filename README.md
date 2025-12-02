# pyjest

`pyjest` is a zero-dependency CLI for running `unittest` suites with
Jest-style reporting, optional watch mode, snapshots, coverage, and
machine-readable reports. It refuses to run unless it detects Python
sources/metadata so you do not accidentally point it at non-Python trees.
Drop it into any repo, `pip install --editable .`, and run the `pyjest`
command to see colorful per-test output, structured summaries, and a nicer
overall experience than `python -m unittest`.

**Highlights**

- Jest-like labels on tests/classes plus readable progress output.
- Watch mode with optional `watchfiles`/`watchdog` backends and change-aware targeting.
- Snapshots (`expect(...).to_match_snapshot()`) with `--updateSnapshot` and optional summaries.
- Coverage.py integration with thresholds, HTML output, and per-file bars.
- JSON/TAP/JUnit reports (`pyjest-report.*`) alongside the console output.
- Inline type hints (`py.typed`) so editors and type checkers work out of the box.

## Usage

```bash
pip install --editable /path/to/pyjest
cd /path/to/your/project
pyjest --pattern 'test_*.py' tests
```

Use `--root /path/to/project` to point the runner at a different working tree
without `cd`-ing first. Targets accept modules, packages, or files ending in
`.py`, `.pyj`, or `.pyjest`; leave them blank to auto-discover tests in `./tests`
(PyJest automatically picks up `.pyj`/`.pyjest` files as part of discovery).

### Discovery and targeting

- Patterns: defaults to `test*.py`, but automatically also tries `*_test.py` and `tests.py` when they exist.
- `.pyj`/`.pyjest` files: discovered alongside normal Python tests; use `--pyjest-only` to ignore `.py` files.
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

### Watch mode

`--watch` keeps PyJest running and re-executes tests when files change. With
`watchfiles` or `watchdog` installed, it uses those for fast notifications;
otherwise it falls back to polling (`--watch-interval`).

- `--onlyChanged`: run only targets inferred from the changed files.
- `--run-failures-first`: in watch mode, rerun previously failing modules before widening the scope.
- `--watch-debounce 0.2`: wait a little after the first change to batch edits.
- `--maxTargetsPerWorker`: when paired with `--maxWorkers`, group targets before fanning out.

Console output shows per-module/class breakdowns by default. Enable more sections
as needed:

- `--report-suite-table`: compact per-suite table with durations
- `--report-outliers`: fastest/slowest tests

### Coverage and reports

- `--coverage`: collect coverage (if `coverage.py` is installed).
- `--coverage-html [DIR]`: write HTML to `coverage_html` (or a custom dir).
- `--coverage-threshold PCT`: fail if total coverage drops below PCT.
- `--coverage-bars`: print per-file coverage bars/sparklines in the console.
- `--report-format json tap junit`: emit machine-readable reports next to your project root (`pyjest-report.json`, `.tap`, `.junit.xml`). Console output is always shown.

### Snapshots

`expect(value).to_match_snapshot()` stores values under `__snapshots__/<module>.snap.json`.
Use `--updateSnapshot` to create/update snapshots and `--snapshot-summary` to print what changed.

### Parallelism (experimental)

`--maxWorkers > 1` fans out multiple targets across threads; `--maxTargetsPerWorker`
bundles targets before dispatching. Keep `--runInBand` for strictly serial runs.

### CLI flags (quick tour)

- `--watch` / `--onlyChanged` / `--watch-interval SECS` / `--watch-debounce SECS`: stay running, rerun on changes, and control how quickly changes trigger reruns.
- `--run-failures-first`: in watch mode, rerun modules that just failed before widening to everything else.
- `--root PATH`: treat PATH as the project root (affects discovery, reports, coverage output).
- `--pattern GLOB` / `--pattern-exclude PATTERN` / `--ignore PATH`: tune discovery to include/exclude files and directories.
- `--pyjest-only`: discover only `.pyj`/`.pyjest` tests (skip regular `.py` tests).
- `--bail` / `--failfast`: stop after the first failure.
- `--runInBand`: force serial execution (current default).
- `--maxWorkers N` + `--maxTargetsPerWorker M`: experimental parallel fan-out; optionally bundle targets before dispatching to workers.
- `--buffer` / `--buf`: capture stdout/stderr during tests so progress output stays clean.
- Progress style: `--progress-fancy {0,1,2}` (or `--fancy-progress`) switches between inline glyphs, compact one-line stats, and a framed table; `--buffer` enables the live spinner status line.
- Coverage: `--coverage` to enable coverage, `--coverage-html [DIR]` to write HTML, `--coverage-threshold PCT` to fail below a percentage, `--coverage-bars` to print per-file bars.
- Reporting: `--report-format console json tap junit` to emit machine-readable reports (`console` always on); `--report-modules` / `--no-report-modules` toggles per-module breakdowns; `--report-suite-table` shows a compact suite table; `--report-outliers` shows fastest/slowest sections.
- Snapshots: `--updateSnapshot` to create/update snapshots; `--snapshot-summary` to print what changed.
- Diffs: `--max-diff-lines N` caps diff size; `--no-color-diffs` disables colored diffs.

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

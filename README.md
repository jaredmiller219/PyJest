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

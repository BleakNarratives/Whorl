# Whorl Testing Notes

## Full local regression

Run from the Whorl repository root:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Latest result on 2026-08-28:

```text
25 tests discovered
24 passed
1 error during test module import
```

All bus, Fire Drill, score feedback, Signal Loom, and Signal Loom demo tests
passed.

## Optional Glint dependency

The sole failure is `tests/test_glint.py`, which imports the optional image-stack
dependencies:

```text
ModuleNotFoundError: No module named 'cv2'
```

The test also requires NumPy. These packages are not part of Whorl's core
`pyproject.toml` dependencies, and no installation was performed during the
regression run. This is an environment/dependency issue, not a regression in
the bus or Signal Loom work.

To run Glint in an environment that intentionally enables the image stack,
provide compatible OpenCV and NumPy packages, then rerun the full discovery.
The core suite remains independently runnable with the Python standard-library
`unittest` runner.

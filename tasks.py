#!/usr/bin/env python3
"""
tasks.py — the one cross-platform task runner.

`Makefile` (Linux/AMD target) and `make.ps1` (Windows) both delegate here, so
the gate logic is identical on every platform. Run directly with:

    python tasks.py <target> [args...]

Targets: setup | schemas | test | run | verify | clean
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
PY = sys.executable

# Keep child processes (validator, pytest, generator) emitting UTF-8 even on a
# cp1252 Windows console.
_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _hr(label: str) -> None:
    print(f"-- {label} ".ljust(58, "-"))


def _run(cmd: list[str], **kw) -> int:
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT), env=_ENV, **kw)


def setup() -> int:
    """Install the package + dev/qa extras into the current environment."""
    return _run([PY, "-m", "pip", "install", "-e", ".[dev,qa]"])


def schemas() -> int:
    """Validate the sidecar JSON Schemas against the hand-written examples."""
    from validation.schema_check import validate_examples

    for line in validate_examples():
        print("  [OK]", line)
    return 0


def test() -> int:
    """Run the unit test suite (skips cleanly if pytest/tests absent)."""
    if not any((ROOT / "tests").glob("test_*.py")):
        print("  (no tests yet)")
        return 0
    return _run([PY, "-m", "pytest", "-q"])


def run(argv: list[str]) -> int:
    """Generate an asset: `python tasks.py run --prompt "..." --seed 1337`."""
    return _run([PY, "-m", "orchestrator.cli", "run", *argv])


def verify() -> int:
    """The full gate suite: schemas + unit tests + (if an asset exists) the validator."""
    _hr("schemas")
    rc = schemas()
    if rc:
        return rc
    _hr("unit tests")
    rc = test()
    if rc:
        return rc
    glb = OUT / "spider_alien.glb"
    if glb.exists():
        _hr("validator (Stage 8)")
        rc = _run([PY, "-m", "validation.validator", str(glb)])
        if rc:
            return rc
    else:
        _hr("validator")
        print("  (no out/ asset yet; run `make run` first)")
    print("\nverify: GREEN")
    return 0


def clean() -> int:
    """Remove generated artifacts in out/ (keeps the directory)."""
    import shutil

    if OUT.exists():
        for p in OUT.iterdir():
            if p.name == ".gitkeep":
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    print("  cleaned out/")
    return 0


TARGETS = {"setup": setup, "schemas": schemas, "test": test, "verify": verify, "clean": clean}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {*TARGETS, "run"}:
        print(__doc__)
        return 2
    target, rest = argv[0], argv[1:]
    if target == "run":
        return run(rest)
    return TARGETS[target]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

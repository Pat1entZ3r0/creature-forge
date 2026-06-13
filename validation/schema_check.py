"""Schema validation for the two sidecar contracts (used by `make verify`)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"

SCHEMAS = {
    "asset_spec": SCHEMA_DIR / "asset_spec.schema.json",
    "godot_setup": SCHEMA_DIR / "godot_setup.schema.json",
}


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_instance(instance: dict | str | Path, kind: str) -> None:
    """Validate a dict (or path to a json file) against the named schema.

    Raises jsonschema.ValidationError on failure.
    """
    if kind not in SCHEMAS:
        raise KeyError(f"unknown schema {kind!r}; known: {sorted(SCHEMAS)}")
    if isinstance(instance, (str, Path)):
        instance = _load(Path(instance))
    schema = _load(SCHEMAS[kind])
    jsonschema.validate(instance, schema)


def validate_examples() -> list[str]:
    """Validate the hand-written example sidecars. Returns a list of pass lines."""
    results = []
    examples = {
        "asset_spec": SCHEMA_DIR / "examples" / "asset_spec.example.json",
        "godot_setup": SCHEMA_DIR / "examples" / "godot_setup.example.json",
    }
    for kind, path in examples.items():
        validate_instance(path, kind)
        results.append(f"schema OK: {kind:<12} <- {path.relative_to(ROOT)}")
    return results


if __name__ == "__main__":
    for line in validate_examples():
        print(line)

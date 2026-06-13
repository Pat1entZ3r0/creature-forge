"""
Stage 1 — spec compiler: natural-language prompt -> asset_spec.json.

Deterministic and rule-based for the documented prompts (a local LLM is the
optional drop-in seam noted below). Whatever fills the schema, the output is then
hard-validated against schemas/asset_spec.schema.json — an out-of-range or
malformed spec is rejected before any geometry is built.
"""

from __future__ import annotations

from conventions import FORWARD_AXIS, UNITS, UP_AXIS
from pipeline.registry import get_archetype
from validation.schema_check import validate_instance

# keyword -> (style, palette, material_model) overrides; deterministic.
_STYLE_RULES = [
    (("ps1", "low-poly", "low poly", "retro"), "low_poly_ps1_horror", "muted_green_purple", "vertex-color"),
    (("realistic", "pbr"), "realistic_pbr", "neutral", "pbr"),
]


def _style_for(prompt: str, archetype) -> tuple[str, str, str]:
    p = prompt.lower()
    for keys, style, palette, material in _STYLE_RULES:
        if any(k in p for k in keys):
            return style, palette, material
    d = archetype.spec_defaults
    return d["style"], d["palette"], d["material_model"]


def compile_spec(prompt: str, seed: int, archetype_name: str) -> dict:
    """Compile a prompt into a schema-valid asset_spec dict.

    NOTE: an LLM could fill this dict instead of the rules below; the schema
    validation at the end is the contract either way (LLM seam).
    """
    archetype = get_archetype(archetype_name)
    d = archetype.spec_defaults
    style, palette, material = _style_for(prompt, archetype)

    spec = {
        "spec_version": "0.1",
        "prompt": prompt,
        "style": style,
        "archetype": archetype_name,
        "seed": int(seed),
        "units": UNITS,
        "up": UP_AXIS,
        "forward": FORWARD_AXIS,
        "target_height_m": d["target_height_m"],
        "tri_budget": d["tri_budget"],
        "vert_budget": d["vert_budget"],
        "texture_budget_px": d["texture_budget_px"],
        "material_model": material,
        "palette": palette,
        "limbs": d["limbs"],
        "locomotion": {"in_place": True},
        "animations": list(d["animations"]),
        "export": "glb",
    }
    validate_instance(spec, "asset_spec")  # gate: reject out-of-range / malformed
    return spec

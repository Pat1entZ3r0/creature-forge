# Architecture

Prompt → playable Godot enemy, in eight stages. The trustworthy core (1, 4-retopo,
5, 6, 7, 8) is CPU-only and hardware-agnostic; only 2 and 3 touch the iGPU. Stages
communicate **only** through the GLB and the two sidecar JSONs — never hidden
in-memory coupling.

| Stage | Input | Output | Gate |
|------:|-------|--------|------|
| 1 Spec compiler | NL prompt + seed | `asset_spec.json` | JSON-Schema validation (`schemas/asset_spec.schema.json`) |
| 2 Concept (opt) | spec | one hero image | VLM archetype/style match · **AMD-only** |
| 3 Mesh gen | spec / image | mesh + albedo | manifold · single component · sane bbox vs `target_height_m` · **TRELLIS AMD-only; procedural fallback always passes** |
| 4 Finishing | dense mesh | retopo'd, decimated, UV'd, baked | tri budget · no UV overlap · no degenerate tris · **AMD/CPU** |
| 5 Rigging | mesh | template skeleton + rigid skin | weights normalized · ≤cap influences · joints inside mesh under FK |
| 6 Animation | rig + mesh | 7 in-place clips | owned by Stage 8 (the planted-foot solver makes checks 6 & 9 pass) |
| 7 Packaging | skeleton+mesh+clips | `model.glb` + 2 sidecars | Khronos `gltf-validator` 0/0/0/0 |
| 8 Validation | GLB + sidecars | `validation_report.json` + measured speeds written back | the 10 checks below, zero warnings |

## The two contracts

- **`<model>.asset_spec.json`** — Stage 1 output, *what was asked*. Schema:
  `schemas/asset_spec.schema.json` (prompt, style, archetype, seed, units `m`,
  up `+Y`, forward `-Z`, target_height_m, tri/vert/texture budgets, material_model,
  locomotion.in_place, animations).
- **`<model>.godot_setup.json`** — Stage 7 output, the *engine contract*. Schema:
  `schemas/godot_setup.schema.json` (collision/hurtbox capsules, locomotion speeds,
  animations with hitbox event windows, hitboxes, state machine, foot_anchors,
  skeleton). Speeds start at 0.0 and are overwritten by Stage 8's measurement.

## The 10 validator checks (`validation/validator.py`)

1. triangle budget vs `tri_budget`
2. skin weights normalized
3. max influences ≤ cap (1 for rigid)
4. loop closure ≈ 0 on every `-loop` clip
5. every skinned joint inside the mesh AABB (structural joints exempt)
6. planted-foot contact: worst stance foot world-Y deviation ≤ 8 mm
7. in-place root drift = 0
8. death clip collapses the body below 0.26 m and rests on the floor
9. ground penetration ≥ −5 mm across ≥64 samples/clip
10. Khronos `gltf-validator`: 0 errors / 0 warnings / 0 infos / 0 hints

The validator is **independent** (its own glTF reader + CPU FK + LBS) — it tests
the artifact, not the author's intentions — and is **archetype-agnostic**: the
arachnid and quadruped pass it unchanged.

## Conventions (`conventions.py`, asserted by the validator)

meters · +Y up · −Z forward · glTF quaternions (xyzw) · identity-bind
translation-only bones · rigid skinning (1 influence) for PS1 · in-place
locomotion with measured speeds written back.

## Orchestration (`orchestrator/`)

`pipeline run` compiles → builds (3/5/6/7) → validates (8) → QA sheet, wrapped in a
content-hash cache (rerun = near-instant restore) and a seed-perturb iteration loop
(gate fail → regenerate with a new seed up to N times → else fail with a per-check
diagnosis). Every run writes `out/run_manifest.json`.

## Adding an archetype

Implement `build_skeleton`, `build_mesh`, `legs`, `leg_rot`, `build_clips`, and
`godot_setup`; register it in `pipeline/registry.py`. The planted-foot solver and
the validator are reused **unchanged** — see `archetypes/quadruped.py`.

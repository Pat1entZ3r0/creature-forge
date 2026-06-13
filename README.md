# creature-forge

A free/open-source, **deterministic, validation-gated** pipeline that turns one
natural-language prompt — *"small venomous spider alien, low-poly PS1 horror
style"* — into a **Godot-ready game enemy**: a rigged, skinned, animated GLB plus
two sidecar JSON contracts, wired into a playable Godot 4.3+ scene with an
`AnimationTree` state machine, collision/hurt volumes, and event-timed attack
hitboxes.

It is built in milestones, each with an explicit acceptance gate. A passing gate
means the check ran and returned green — never an asserted success. See
[`STATUS.md`](STATUS.md) for the honest, per-stage state.

## Dual-target reality

The pipeline is designed for an **AMD Ryzen AI Max+ 395 "Strix Halo"** box
(Radeon 8060S iGPU, `gfx1151`, 128 GB unified memory, Ubuntu 24.04, ROCm 7.x).
But the trustworthy core is hardware-agnostic:

- **CPU-only core — Stages 1, 4-retopo, 5, 6, 7, 8** — runs and gate-passes on any
  machine, including the Windows box this was built on. This is the
  differentiating, correctness-critical layer, and it carries **no GPU risk**.
- **GPU stages — 2 (FLUX), 3 (TRELLIS.2)** — need the AMD iGPU + ROCm. They are
  implemented for that target (see [`docs/HARDWARE.md`](docs/HARDWARE.md)) and
  fall back to the deterministic **procedural Stage-3 tier** anywhere the GPU
  stack isn't available. The fallback is real and passes every gate on its own.

## Quickstart

```bash
# Linux / AMD target
make setup                       # install the package + dev/qa extras
make run ARGS='--prompt "small venomous spider alien, low-poly PS1 horror style" --seed 1337'
make verify                      # schemas + unit tests + the 10-check validator
```

```powershell
# Windows (identical gate logic; uses .\.venv if present)
python -m venv .venv; .\.venv\Scripts\python -m pip install -e ".[dev,qa]"
.\make.ps1 run --prompt "small venomous spider alien, low-poly PS1 horror style" --seed 1337
.\make.ps1 verify
```

`make`/`make.ps1` both delegate to `tasks.py`, so the gate is identical on every
platform.

## Layout

```
conventions.py     Non-negotiable globals (units, axes, quat order, limits) + math kit.
schemas/           JSON Schemas for both sidecar contracts + hand-written examples.
config/            pipeline.toml — seeds, model versions, GPU/ROCm settings.
archetypes/        Per-archetype skeleton templates + gait graphs (arachnid, quadruped).
pipeline/          Stages 1-7 as modules (procedural Stage-3 + AMD TRELLIS path).
validation/        Stage 8: the independent validator (own glTF reader + FK + LBS).
orchestrator/      CLI, content-hash cache, seed-perturb iteration loop, run manifest.
godot/             The four Godot 4.3+ GDScript files.
scripts/           preflight.py — ROCm/gfx1151 hardware bring-up (AMD target).
dashboard/         Web run-viewer over out/ artifacts.
tests/             Unit tests. The validator is the integration test.
out/               Generated artifacts (GLB, sidecars, reports, QA sheet).
```

## The contracts

Two sidecars travel with the GLB and are the single source of truth:
`<model>.asset_spec.json` (what was asked — Stage 1) and
`<model>.godot_setup.json` (the engine contract — Stage 7). Both are schema-
validated; their shapes live in [`schemas/`](schemas/).

Conventions (enforced by the validator): meters, +Y up, −Z forward, glTF
quaternions, identity-bind translation-only bones, rigid skinning for PS1,
in-place locomotion with measured speeds written back by Stage 8.

Licenses are verified in [`docs/LICENSES.md`](docs/LICENSES.md); the architecture
critique that motivated this design is in
[`docs/IMPROVED_PIPELINE.md`](docs/IMPROVED_PIPELINE.md).

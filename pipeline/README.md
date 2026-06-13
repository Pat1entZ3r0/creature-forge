# Spider Alien — AI Asset Pipeline Proof of Concept

This is a working proof of concept for the hard, differentiating layers of a "prompt → playable Godot enemy" pipeline: spec compilation, archetype-template rigging, procedural animation with world-space ground-contact solving, spec-compliant GLB packaging, engine-contract sidecars, automated validation gates, and Godot 4 wiring. It was built to test the claim that such a pipeline is realistic with free/open components — the verdict and full critique live in `IMPROVED_PIPELINE.md`.

One stage is deliberately stubbed: ML image-to-3D mesh generation (no GPU in the build environment). A deterministic procedural arachnid generator stands in for it, producing exactly the artifact a real mesh-gen stage would need to produce — same conventions, same budgets, same downstream contract — so the rig/animate/package/validate/integrate layers it feeds are the real thing, not mockups.

The test prompt, taken from the original pipeline document: *"small venomous spider alien, low-poly PS1 horror style."*

## What's in here

`spider_alien.glb` is the deliverable asset: 288 triangles (budget 1,800), 576 vertices, 22 joints, rigid per-vertex skinning, flat-shaded vertex colors, 7 animation clips (`idle-loop`, `walk-loop`, `run-loop`, `attack_01`, `attack_02`, `hit`, `death`), authored in meters, +Y up, −Z forward, in-place locomotion. It passes the official Khronos glTF validator with zero errors, warnings, infos, or hints (`khronos_report.json`).

`spider_alien.asset_spec.json` is the Stage-1 output — the machine-readable spec compiled from the prompt (style, budgets, archetype, seed). `spider_alien.godot_setup.json` is the Stage-7 engine contract: collision and hurtbox capsules, two bone-attached attack hitboxes with damage values and active time windows, a full animation state machine with crossfade times, foot anchor positions, and locomotion speeds. The speeds in that file are not authored guesses — they were **measured from the GLB by the validator** (walk 0.216 m/s, run 0.532 m/s) and written back, closing the QA loop.

`generate_creature.py` builds the GLB and both sidecars from scratch (hand-written glTF 2.0 writer, no exporter library). `validate_asset.py` is the Stage-8 gate: it re-parses the GLB from disk with its own glTF reader, runs CPU forward kinematics and linear-blend skinning, and checks ten properties. `run_khronos_validator.mjs` runs the official Khronos validator. `validation_report.json` holds the results; `qa_contact_sheet.png` is a rendered frame grid across all seven clips for eyeball QA.

The `godot/` folder holds four GDScript files described below.

## Reproduce the Python side

Requires Python 3 with numpy (and matplotlib for the contact sheet), plus Node for the Khronos check.

```bash
python3 generate_creature.py        # writes out/spider_alien.glb + both sidecars (deterministic, seed 1337)
python3 validate_asset.py           # 10-check gate + measured-speed write-back + contact sheet
npm install gltf-validator          # once
node run_khronos_validator.mjs      # official spec conformance
```

## Validation results

All ten checks pass with zero warnings. Triangle count 288 against a 1,800 budget. All skin weights normalized, max 1 influence per vertex (rigid skinning by design). Loop closure error 0.0 on all looping clips. All 21 skinned joints stay inside the mesh volume across every sampled pose (the unskinned structural root is exempt). Worst planted-foot hover across walk and run is 3.28 mm against an 8 mm limit. Root drift 0.0 (in-place contract). The death clip collapses the body to 0.252 m, under the 0.26 m threshold, and the corpse rests on the floor. Worst ground penetration anywhere in a 64-sample-per-clip stress sweep is −4.64 mm against a −5 mm limit. Khronos: 0/0/0/0.

The two contact metrics are the interesting ones. Naïve joint-space animation authoring produced 14–19 mm of foot hover and up to 95 mm of ground penetration during the death curl. Those numbers are why the pipeline document's missing QA loop matters: ground contact is a **world-space constraint** that joint-space keyframes cannot guarantee. The fix in `generate_creature.py` is a planted-foot solver — for each leg at each key, it bisects the femur lift angle (44 iterations over [−40°, 82°]) so the leg's lowest skinned vertex, computed by exact FK against the real mesh, lands on the ground plane. The death clip additionally clamps body height per key so curling legs never punch through the floor.

## Run it in Godot 4.3+

No engine was available in the build environment, so the four scripts in `godot/` are **carefully written but unverified in-engine**. Treat them as a strong first draft. Expected setup:

```text
res://
├── assets/
│   ├── spider_alien.glb
│   └── spider_alien.godot_setup.json
└── scripts/
    ├── enemy_factory.gd
    ├── enemy_controller.gd
    ├── enemy_post_import.gd
    └── demo_runtime.gd
```

Create an empty Godot 4.3+ project, copy the files into that layout, create a new scene with a plain `Node3D` root, attach `demo_runtime.gd` to it, save it, and set it as the main scene. Press F5. The demo constructs the floor, sun, sky, camera, and UI entirely in code, loads the GLB at **runtime** via `GLTFDocument` (proving the no-editor path used for modding or procedural spawning), and hands it to `EnemyFactory.build()`.

`enemy_factory.gd` turns the GLB scene plus the sidecar dictionary into a playable `CharacterBody3D`: capsule collision and hurtbox from the JSON, `BoneAttachment3D`-mounted attack hitbox areas on the head bone, defensive loop-mode enforcement, and an `AnimationTree` whose `AnimationNodeStateMachine` is built edge-by-edge from the sidecar — one-shot states get `AT_END` auto-return transitions to idle, death is terminal and holds its last pose. `enemy_controller.gd` drives it: `travel()`-based state changes, capsule translation at the measured speeds only while the state machine is actually in a moving state (eliminating foot-slide by construction), per-physics-tick polling of the playback position against the JSON hitbox windows, damage and death handling, and gameplay signals. `enemy_post_import.gd` is the editor-import alternative — an `EditorScenePostImport` hook that binds the sidecar to the imported scene, which is the correct Godot integration point rather than a from-scratch `EditorImportPlugin`.

Demo keys: 1 idle, 2 walk, 3 run, 4 slam attack, 5 lunge bite, 6 take 8 damage (third hit kills at 22 hp), 7 instant kill, Q/E turn, R respawn.

## Honest limitations

The ML stages (concept image, image-to-3D) are stubbed; their I/O contracts are defined in `IMPROVED_PIPELINE.md` so TRELLIS.2 + retopo can be slotted in where the procedural generator now sits. The GDScript is unverified in-engine. One archetype (arachnid) is implemented; the per-archetype template approach is the point, but each new archetype is real work. Skinning is rigid (1 bone per vertex) — correct for PS1 style, insufficient for smooth organic deformation. Materials are vertex colors only; the PS1 look is intended to be completed shader-side in Godot (affine warp, dither, fog), which is the cheaper and more uniform place to do it. The attack-from-walk path briefly settles through idle because the sidecar only authors idle→attack edges — a data fix, not a code fix, and deliberately left to demonstrate that the JSON is the single source of truth.

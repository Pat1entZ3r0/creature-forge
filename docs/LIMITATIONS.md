# Honest limitations

What this pipeline does NOT do, or does only conditionally. Kept explicit so the
"free, deterministic, validation-gated" claim stays truthful.

## Hardware / GPU
- **The GPU stages (2 FLUX, 3 TRELLIS.2) were not executed here.** This was built
  on a Windows box with no ROCm; they are implemented for the AMD Strix Halo /
  gfx1151 target and are verified only there. Off-target they raise `GpuUnavailable`
  and the pipeline falls back to the procedural Stage-3 tier — recorded in
  `STATUS.md`, never faked.
- The gfx1151 source build of TRELLIS's custom extensions (`o_voxel`, `cumesh`,
  `flexgemm`, `nvdiffrast`) is **real, uncertain work** — validated forks exist for
  gfx1100/RDNA4, not gfx1151. Treat Milestone 4's live tier as unproven until a
  green preflight + a generated spider that passes all 10 checks on the target.

## In-engine
- **The four GDScript files parse and lint clean but were NOT run in Godot.**
  In-engine behaviour (states play, feet planted, hitbox windows accurate) requires
  a human in Godot 4.3+ — marked human-verify-pending in `STATUS.md`. We can
  validate the GLB exhaustively offline; we cannot certify GDScript without the engine.

## Modeling / rigging
- **Procedural Stage-3 fallback is box geometry**, not organic — correct for proving
  the rig/animate/validate spine, not a substitute for TRELLIS output.
- **Rigid skinning (1 influence)** — correct for PS1, insufficient for smooth organic
  deformation (≤4-influence LBS is supported by the validator but not yet authored).
- The generated-mesh rigger (Stage 5 on a TRELLIS mesh) uses **nearest-bone landmark
  fitting**; on adversarial topology it can fail, in which case the orchestrator
  falls back to the procedural mesh for that run and logs it. UniRig is the intended
  robust assist and is wired as a guarded seam, not yet exercised.

## Animation
- **Non-humanoid procedural gait only.** Humanoids need a Kimodo → SMPL → game-rig
  **retargeting stage** that is named but not built — do not assume humanoid support.
- Two archetypes ship (arachnid, quadruped). Each new archetype is real authoring
  work, even though the solver and validator are reused unchanged.

## Materials
- **Vertex colors only.** The PS1 look (affine warp, vertex snap, dither, fog) is
  intended as one shared Godot material, done in-engine — not baked into the asset.

## Spec compilation
- Stage 1 is a **deterministic rule-based compiler** for the documented prompts; an
  LLM front-end is a documented seam (`pipeline/stage1_spec.py`) but not wired, so
  arbitrary free-form prompts are not yet supported end to end.

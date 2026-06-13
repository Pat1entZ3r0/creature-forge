# STATUS

Honest per-stage and per-milestone state. **No stage is faked.** A stage marked
"procedural fallback" produces a real, gate-passing artifact via deterministic
assembly; a stage marked "AMD-only" is implemented for the target hardware and
cannot be executed or verified on this Windows build box.

Build box: **Windows 11** (Python 3.13, Node 22). The target deployment box is
the AMD Ryzen AI Max+ 395 "Strix Halo" / Ubuntu 24.04 / ROCm described in
`docs/HARDWARE.md`. The correctness-critical core (Stages 1, 4-retopo, 5, 6, 7, 8)
is CPU-only and runs and gate-passes here.

## Stages

| Stage | What | Implemented | Gate | Verified where | Notes |
|------:|------|:-----------:|:----:|----------------|-------|
| 1 | Spec compiler | ✅ | ✅ | Windows | rule-based + schema-validated; LLM seam noted |
| 2 | Concept image (FLUX) | code ✅ · 🟠 AMD-only | n/a here | target only | FLUX.1-schnell via diffusers; guarded, optional |
| 3 | Mesh gen | ✅ (procedural) · code ✅ (TRELLIS) | ✅ procedural | Windows | 🟠 procedural fallback ships here; TRELLIS.2 path is AMD-only, falls back cleanly |
| 4 | Finishing (retopo/decimate/UV/bake) | code ✅ · 🟠 AMD-only | n/a here | target only | Instant Meshes + Blender headless bake; guarded |
| 5 | Rigging (template fit) | ✅ | ✅ | Windows | arachnid template, rigid skin, 22 joints |
| 6 | Procedural animation + planted-foot solver | ✅ | ✅ | Windows | alt-tetrapod gait + solver; foot 3.28mm, pen -4.6mm |
| 7 | Packaging (GLB + 2 sidecars) | ✅ | ✅ | Windows | byte-deterministic GLB; Khronos 0/0/0/0 |
| 8 | Validation + speed write-back | ✅ | ✅ | Windows (CPU) | independent reader; 10 checks; Khronos 0/0/0/0 on fixture |

## Milestones

| # | Milestone | State | Gate |
|--:|-----------|:-----:|------|
| 0 | Scaffold + contracts | ✅ gate-passing | `make verify` validates schemas |
| 0.5 | Hardware preflight (ROCm/gfx1151) | ⬜ | AMD-only; honest skip on Windows |
| 1 | Validator first | ✅ gate-passing | PASS good fixture, FAIL broken fixture (foot 6cm through floor) |
| 2 | Spider end-to-end (procedural Stage 3) | ✅ gate-passing | 10/10 checks; byte-deterministic; QA sheet rendered |
| 3 | Godot integration layer | ✅ parse/lint · 🟣 in-engine pending | gdparse+gdlint clean; in-engine NOT self-certifiable — awaits a human in Godot 4.3+ |
| 4 | TRELLIS.2 + Stages 2 & 4 | 🟠 AMD-only; ✅ fallback here | generative path implemented + guarded; off-target falls back to procedural and validates 10/10 (honest) |
| 5 | Orchestrator (cache + iteration loop) | ✅ gate-passing | cold validates; warm = cache hit (0.007s vs 1.55s); retry loop perturbs seed, recovers/exhausts w/ diagnosis; run manifest |
| 6 | Quadruped archetype + docs | ✅ gate-passing | quadruped 10/10 (foot 2.86mm, pen -4.4mm) with solver + validator UNCHANGED; docs complete |
| + | Run dashboard (web) | ⬜ | visualizes out/ artifacts |

Legend: ⬜ not started · 🟡 in progress · ✅ gate-passing · 🟣 human-verified · 🟠 fallback/AMD-only

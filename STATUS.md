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
| 2 | Concept image (FLUX) | ⬜ | ⬜ | — | M4, AMD-only, optional |
| 3 | Mesh gen | ✅ | ✅ | Windows | 🟠 procedural fallback tier (real, gate-passing); TRELLIS.2 = M4 AMD-only |
| 4 | Finishing (retopo/decimate/UV/bake) | ⬜ | ⬜ | — | M4; Blender bake AMD-or-CPU |
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
| 3 | Godot integration layer | ⬜ | parse/lint; **in-engine = human-verified** |
| 4 | TRELLIS.2 + Stages 2 & 4 | ⬜ | AMD-only; procedural fallback acceptable here |
| 5 | Orchestrator (cache + iteration loop) | ⬜ | cold run validates, warm run cached, retry loop logs |
| 6 | Quadruped archetype + docs | ⬜ | quadruped passes all 10 checks, solver/validator unchanged |
| + | Run dashboard (web) | ⬜ | visualizes out/ artifacts |

Legend: ⬜ not started · 🟡 in progress · ✅ gate-passing · 🟣 human-verified · 🟠 fallback/AMD-only

# Improved Pipeline: Prompt → Playable Godot Enemy

Verdict up front: the pipeline described in the original document is **realistic in a constrained form and was partially proven here**, but not as written. The document's architecture is directionally right — spec compiler, generative mesh stage, auto-rigging, animation synthesis, Godot packaging — and several of its specific claims are wrong or self-contradictory in ways that would sink a naive implementation. This document is the corrected architecture. The proof-of-concept in this folder implements stages 1, 5, 6, 7, and 8 for real and stubs stage 3 with a contract-identical procedural generator.

## What the original gets right

The decomposition into a spec-compilation front end, a generative middle, and an engine-integration back end is correct, and so is the core insight that the *engine contract* (state machines, hitboxes, import automation) is where most "AI asset" projects die — not in mesh quality. Treating hitbox timing as sidecar data rather than engine-side hand-tuning is genuinely good design, and the POC keeps it. The choice of glTF/GLB as the interchange spine is right. The instinct that everything must be validated rather than trusted is present in spirit, even though the document never specifies a single concrete check.

## Layer-by-layer corrections

**Layer 1 — spec compiler.** The document's spec schema has no units, no axis convention, no scale, no root-motion policy, and no material contract. Those five omissions are exactly the things that make a downstream GLB silently wrong in-engine (a spider imported at 100× scale, facing +Z, sliding on its feet). The corrected schema below makes them mandatory fields. Everything else in the original schema (style, budget, archetype) survives.

**Layer 2 — reference sheets.** Multi-view "character sheets" via ComfyUI are overstated as a requirement. Modern image-to-3D models condition on a single image and hallucinate novel views internally; a multi-view sheet that isn't pixel-consistent (and diffusion sheets aren't) actively hurts. The corrected stage produces one hero image, optionally none — TRELLIS.2 also accepts text directly.

**Layer 3 — image-to-3D.** The document's lineup (TripoSR, Stable Fast 3D, Hunyuan3D) omits the strongest open option, Microsoft's TRELLIS / TRELLIS.2 (MIT code *and* weights, native textured-mesh output, handles complex topology). It also ignores the topology problem entirely: these models emit marching-cubes-style triangle soup, so a retopology pass (Instant Meshes or QuadriFlow) is not optional for anything that must deform. And two of its three picks have license problems for a "free pipeline" claim — see the table.

**Layer 4 — game-asset finishing.** The document proposes authoring LOD chains; Godot 4 generates LODs automatically at import, so hand-built chains are wasted effort for this target engine. It also conflates two different PS1 treatments: asset-side (low poly counts, palette-quantized textures, vertex colors — the generator's job) and shader-side (affine texture warp, vertex snapping, dithering, fog — Godot material's job). Splitting them matters because the shader-side half is uniform across all assets and should be done once, in-engine.

**Layer 5 — rigging, the self-contradiction.** The document recommends *template-free* riggers (RigAnything-style) while simultaneously building its whole animation plan on *archetypes* with known skeletons. Those are opposite bets. If downstream animation assumes a canonical arachnid skeleton, the rigger must be archetype-*constrained*: fit a known template skeleton to the mesh, don't discover a novel one. The corrected design makes archetype templates primary and uses UniRig (MIT, released skeleton+skinning checkpoint) as the assist and as the general-mesh path. The POC's translation-only, identity-bind-rotation skeleton convention exists for this reason — fitted templates and validation FK both get dramatically simpler.

**Layer 6 — animation and Godot integration.** Three concrete corrections. First, the motion-diffusion models the document leans on (including NVIDIA's Kimodo, which is real, Apache-2.0, and trained on 700 hours of commercially licensed mocap) output **SMPL/SMPL-X-family humanoid skeletons**; the document never mentions the SMPL→game-rig retargeting stage, which is a project in itself, and none of these models will animate a spider at all — non-humanoids need procedural synthesis, which the POC proves out. Second, the correct Godot import hook is `EditorScenePostImport` (or `GLTFDocumentExtension` for deep surgery), not a from-scratch `EditorImportPlugin`; Godot already imports glTF, you only annotate the result. Third, locomotion should ship in-place with speeds as sidecar data — root motion is harder to validate, harder to blend, and Godot's `CharacterBody3D` workflow favors in-place. Looping is communicated with the importer-honored `-loop` name suffix *and* enforced from the sidecar defensively.

**Cross-cutting gaps.** The original has no iteration loop (what happens when a stage's output is bad?), no determinism story (no seeds anywhere), no compute budget, no license audit, and no fallback when ML output is unusable. The corrected design adds: seeds plumbed through every stage; per-stage caching keyed on spec hash; validation gates whose failure triggers regeneration with seed/param perturbation; a license table; a hardware table; and part-based procedural assembly as the deterministic fallback tier — which is what the POC's generator is.

## The corrected eight-stage architecture

**Stage 1 — Spec compiler.** Input: natural-language prompt. Output: `asset_spec.json`. An LLM fills a strict JSON schema, then a non-LLM validator rejects out-of-range values. Mandatory fields beyond the original's style/budget/archetype: `units` (meters), `up_axis` (+Y), `forward` (−Z), `target_height_m`, `tri_budget`, `vert_budget`, `texture_budget_px`, `material_model` (vertex-color | albedo-only | PBR), `locomotion` (in_place), `seed`. Gate: schema validation.

**Stage 2 — Concept reference (optional).** Input: spec. Output: one hero image. FLUX.1-schnell or SDXL locally; skip entirely when the mesh stage accepts text. Gate: a VLM check that the image matches archetype and style tags.

**Stage 3 — Mesh generation, three tiers.** Tier A: TRELLIS.2 (image or text → textured mesh, MIT). Tier B: territory-permitting alternates (Hunyuan3D where its license applies). Tier C: deterministic part-based procedural assembly per archetype — always available, always passes gates, and is the tier this POC implements. Output: mesh + albedo, roughly watertight. Gate: manifoldness above threshold, single dominant connected component, bounding box sane against `target_height_m`.

**Stage 4 — Game-asset finishing.** Retopo (Instant Meshes / QuadriFlow) → decimate to `tri_budget` → UV unwrap → bake albedo from the tier-A source → optional palette quantization for PS1 asset-side style. No LOD authoring; Godot 4 auto-LOD covers it. Shader-side PS1 (affine warp, vertex snap, dither, fog) is explicitly deferred to one shared Godot material. Gate: budget compliance, UV overlap check, no degenerate triangles.

**Stage 5 — Rigging.** Primary: fit the archetype's canonical template skeleton (translation-only bones, identity bind rotations) to the mesh via landmark heuristics; skin rigidly for PS1 style or LBS with ≤4 influences otherwise. Assist/general path: UniRig. Gate: weight normalization, influence cap, every skinned joint inside the mesh volume under FK across a pose sweep.

**Stage 6 — Animation.** Non-humanoids: procedural gait synthesis from the archetype's gait graph — phase-offset stepping (alternating tetrapod for arachnids), with the **planted-foot world-space solver** the POC introduced: per leg per key, bisect the lift joint so the leg's lowest skinned vertex (exact FK against the real mesh) lands on the ground plane. One-shot clips are densified and solved per key; the death clip clamps body height so curling limbs never penetrate. Humanoids: Kimodo/AniGen-class diffusion **plus an explicit SMPL→template retarget stage** (named, budgeted, and tested as its own component). All clips in place, full controlled-bone-set keying, `-loop` suffix on loops. Gate: stage 8 owns it.

**Stage 7 — Packaging.** Hand- or library-written GLB plus two sidecars. `asset_spec.json` records what was asked for; `godot_setup.json` is the engine contract: collision/hurtbox primitives, bone-attached hitboxes with damage and `hitbox_on`/`hitbox_off` event times, the full state machine (states, transitions, crossfades), foot anchors, locomotion speeds, health. Gate: official Khronos glTF validator, zero errors and zero warnings.

**Stage 8 — Validation and write-back.** An independent reader (not the writer's code paths) re-parses the GLB, runs CPU FK + linear-blend skinning, and checks: triangle budget, weight normalization, influence cap, loop closure on `-loop` clips, joint containment, planted-foot contact error (≤8 mm), in-place root drift (= 0), death collapse height, ground penetration across a dense stress sweep (≥ −5 mm), plus the Khronos report merged in. It then **measures** locomotion speed from foot cadence and stride and writes it back into `godot_setup.json` — the engine consumes measured truth, not authored intent. Any failure loops to the owning stage with a perturbed seed. This closed loop is the single biggest addition over the original document, and the POC's numbers show why: naive joint-space authoring produced 14–19 mm foot hover and −95 mm death-clip penetration; the solver plus this gate brought those to 3.28 mm and −4.4 mm. Ground contact is a world-space constraint; joint-space keyframes cannot promise it, only a gate can.

## License reality check (verified June 2026)

| Component | Role | License | Catch for a "free" pipeline |
|---|---|---|---|
| TRELLIS / TRELLIS.2 (Microsoft) | image/text → 3D | MIT (code + weights) | none — the strongest open option, omitted by the original |
| UniRig (Tsinghua/VAST) | auto-rigging | MIT | released checkpoint is the Articulation-XL2.0 skeleton+skinning variant |
| Hunyuan3D 2.0 / 2.1 (Tencent) | image → 3D | Tencent community license | **territory-excluded: EU, UK, South Korea** — not "free" for a large share of users |
| Stable Fast 3D (Stability) | image → 3D | Stability community license | free only under US$1M annual revenue, attribution required |
| TripoSR | image → 3D | MIT | quality now well behind TRELLIS-class models |
| FLUX.1-schnell / FLUX.1-dev | concept image | Apache-2.0 / non-commercial | use schnell for commercial work, not dev |
| Kimodo (NVIDIA, 2026) | motion diffusion | Apache-2.0 | humanoid skeleton families only (SOMA/SMPL-X/Unitree G1); no non-humanoids |
| Instant Meshes / QuadriFlow | retopo | open source | none |
| Godot 4 | engine | MIT | none |

## Hardware budget the original never gave

| Stage | Typical VRAM | Notes |
|---|---|---|
| FLUX.1 concept image | 12–24 GB | schnell variant, quantized fits lower |
| TRELLIS.2 mesh gen | ~16–24 GB class | 4B parameters; consumer 24 GB cards are the comfortable target |
| Hunyuan3D 2.x | ~10–16 GB | where licensable |
| Kimodo motion | ~17 GB | humanoids only |
| Retopo / rig / animate / package / validate | CPU | the entire POC in this folder ran with no GPU at all |

The practical implication: one 24 GB consumer GPU runs every ML stage sequentially, and everything that makes the pipeline *trustworthy* — stages 5 through 8 — is CPU-only.

## Why arachnid-first is the right MVP

Three reasons. The procedural gait path is the genuinely differentiating technology and the only path that works for non-humanoids at all, so proving it first de-risks the most. An eight-legged archetype maximally stresses the planted-foot solver (eight simultaneous world-space contact constraints under a bobbing, pitching body) — if the solver holds there, quadrupeds are easy. And it entirely dodges the SMPL→game-rig retargeting project that humanoid motion diffusion drags in, which is the single largest unbudgeted work item in the original document. Sequence: arachnid (done, this POC) → quadruped archetype (new gait graph, same solver) → humanoid (retarget stage as its own tested component, Kimodo behind it).

## What was actually proven here

Stages 1, 5, 6, 7, 8 end to end on the document's own example prompt: a 288-triangle, 22-joint, 7-clip spider alien whose GLB passes the official Khronos validator at 0/0/0/0 and a ten-check semantic gate at 10/10 with zero warnings, whose locomotion speeds in the engine contract are measured rather than asserted, and whose Godot integration is written against the exact APIs named above. Stage 3 ran in its deterministic fallback tier. Nothing in the remaining ML tiers changes any downstream contract — they slot into the same `mesh + albedo in, validated GLB out` socket the fallback already fills.

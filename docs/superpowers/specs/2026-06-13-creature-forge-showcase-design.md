# creature-forge — Pipeline Showcase Site (Design)

Date: 2026-06-13

## Purpose

An interactive web showcase for the **creature-forge** proof-of-concept: an AI
asset pipeline that turns the prompt *"small venomous spider alien, low-poly PS1
horror style"* into a fully-rigged, validated, Godot-ready game enemy. The site
is a cinematic showpiece that **respects the engineering depth** — the 8-stage
architecture, the closed validation loop, and the honest critique are
first-class content, not decoration.

Audience: peers, recruiters, and technically-literate readers who can appreciate
both the visual craft and the rigor (Khronos 0/0/0/0, a planted-foot world-space
solver, measured-not-asserted locomotion speeds).

## Aesthetic Direction

**"Specimen under examination" — dark forensic containment lab × PS1 horror.**

- **Palette** (pulled from the actual asset): void/aubergine background
  (`#0c0a14`–`#171228`), bone-white body text (`#e8e6df`), a single toxic
  bioluminescent green accent (`#7CFF9B`) for the eyes/HUD/PASS states, and a
  muted bruise-purple secondary. High contrast, near-black, one sharp accent.
  Explicitly NOT purple-gradient-on-white AI cliché.
- **Typography**: a distinctive technical monospace for HUD/data/labels
  (Departure Mono or TX-02 class), paired with a sharp characterful display face
  for headers. Never Inter / Roboto / system fonts.
- **Atmosphere**: subtle scanlines, film grain, CRT vignette, faint blueprint
  grid. The spider lives in a "containment viewport" with a live green wireframe
  HUD reading tri/vert/joint counts.
- **Motion**: one well-orchestrated staggered boot-up reveal on load;
  scroll-triggered reveals per act; surprising hover states. CSS/Motion, no
  scattered noise.

## Structure — single-page scrollytelling, 7 acts

1. **Hero** — full-bleed live spider through the custom PS1 shader, slow idle
   rotation, staggered boot reveal. Title `creature-forge`, the real prompt as
   subtitle, scroll cue.
2. **Prompt → Spec** — the natural-language prompt visibly compiling into
   `asset_spec.json` (Stage 1). Show the mandatory-field corrections (units,
   axes, budgets, locomotion, seed).
3. **The 8-Stage Pipeline** — interactive stage-by-stage walk-through. Each stage
   carries its *correction over the original document* (the substance from
   `IMPROVED_PIPELINE.md`). Stage 3 flagged as the stubbed/procedural tier.
4. **The Specimen** — the large interactive viewer: orbit camera, a dock of all
   **7 clip buttons** (idle-loop / walk-loop / run-loop / attack_01 / attack_02 /
   hit / death), live tri/vert/joint readout, wireframe + PS1-shader toggles.
5. **The Validation Gate** — the 10 checks animating to PASS with real numbers,
   climaxing on the **solver before/after**: naïve joint-space authoring gave
   14–19 mm foot hover and −95 mm death-clip penetration → the planted-foot
   solver brought those to **3.28 mm** and **−4.4 mm**. The technical peak.
6. **Engine Contract** — `godot_setup.json` visualized: the animation
   state-machine graph, bone-attached hitbox timing windows, and the *measured*
   locomotion speeds (walk 0.216 / run 0.532 m/s) written back by QA.
7. **The Verdict** — honest limitations, the license reality-check table, and the
   hardware budget. "What was actually proven."

Footer: prompt → asset recap, links.

## Technical Architecture

- **Vite + React + TypeScript.**
- **react-three-fiber** + **@react-three/drei** for the 3D scene; **Motion**
  (framer-motion) for reveal/scroll animation.
- **Custom PS1 `shaderMaterial`**: vertex snapping (quantize clip-space position
  to a low-res grid), affine / perspective-incorrect attribute interpolation,
  ordered (Bayer) dither, distance fog. Directly demonstrates the shader-side
  PS1 look the docs say belongs in-engine.
- `spider_alien.glb` served from `public/`; animation clips driven by the GLB's
  own tracks via drei `useAnimations`.
- **Single source of truth**: every displayed statistic is imported from the real
  JSON files (`validation_report.json`, `asset_spec.json`,
  `spider_alien.godot_setup.json`, `khronos_report.json`) copied into the app.
  No hand-typed stats — honors the pipeline's own principle.

## Component Boundaries

- `scene/SpiderViewer` — canvas, lights, camera controls, fog; owns the loaded
  GLB + animation mixer; exposes clip selection + shader/wireframe toggles.
- `scene/ps1Material` — the PS1 shader material (isolated, testable in isolation).
- `acts/*` — one component per act, each fed by typed data selectors.
- `data/` — typed imports of the JSON sidecars + small derived selectors
  (e.g. the checks list, the solver before/after pairs).
- `ui/` — shared atmosphere primitives (Grain, Scanlines, Grid, StatReadout,
  SectionReveal).

## Success Criteria

- `npm install && npm run dev` runs clean; `npm run build` produces a static
  bundle with no type errors.
- The live spider loads and all 7 clips play with the PS1 shader.
- Every number on the page traces back to a JSON file (no magic literals).
- Distinctive, cohesive aesthetic — passes the "not generic AI slop" bar.
- Committed and pushed to a new GitHub repo.

## Out of Scope (YAGNI)

- No backend, no CMS, no routing (single page).
- No Godot runtime in-browser (the .gd scripts are shown as artifacts, not run).
- No multi-archetype support — this showcases the one proven asset.

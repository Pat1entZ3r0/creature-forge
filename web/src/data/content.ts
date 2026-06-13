// Editorial content distilled from README.md and IMPROVED_PIPELINE.md.
// Prose is authored; every number lives in the JSON (see ./index.ts).

export type Stage = {
  n: number;
  title: string;
  io: string;
  body: string;
  correction: string;
  status: "real" | "stub";
  gate: string;
};

export const stages: Stage[] = [
  {
    n: 1,
    title: "Spec compiler",
    io: "prompt → asset_spec.json",
    body: "An LLM fills a strict JSON schema; a non-LLM validator rejects out-of-range values.",
    correction:
      "The original schema had no units, axis convention, scale, root-motion policy, or material contract — exactly the five omissions that make a GLB silently wrong in-engine. All five are now mandatory.",
    status: "real",
    gate: "schema validation",
  },
  {
    n: 2,
    title: "Concept reference",
    io: "spec → one hero image (optional)",
    body: "FLUX.1-schnell or SDXL locally — skipped entirely when the mesh stage accepts text.",
    correction:
      "Multi-view ‘character sheets’ are overstated. Modern image-to-3D conditions on a single image and hallucinates views; an inconsistent diffusion sheet actively hurts.",
    status: "real",
    gate: "VLM archetype/style match",
  },
  {
    n: 3,
    title: "Mesh generation",
    io: "image/text → mesh + albedo",
    body: "Tier A TRELLIS.2 (MIT, text or image). Tier C: deterministic part-based procedural assembly per archetype — the tier this POC ships.",
    correction:
      "The original lineup omitted TRELLIS.2 (the strongest open option) and ignored topology entirely — marching-cubes soup needs a retopo pass before it can deform.",
    status: "stub",
    gate: "manifoldness · single component · sane bbox",
  },
  {
    n: 4,
    title: "Game-asset finishing",
    io: "retopo → decimate → UV → bake",
    body: "Decimate to budget, unwrap, bake albedo, optional palette quantization for asset-side PS1.",
    correction:
      "No hand-built LOD chains — Godot 4 auto-LODs at import. Shader-side PS1 (affine warp, vertex snap, dither, fog) is deferred to one shared material, done once in-engine.",
    status: "real",
    gate: "budget · UV overlap · no degenerates",
  },
  {
    n: 5,
    title: "Rigging",
    io: "mesh → skeleton + skin",
    body: "Fit the archetype's canonical template skeleton (translation-only bones, identity bind rotations) to the mesh; rigid-skin for PS1.",
    correction:
      "The original recommended template-free riggers while basing all animation on known archetypes — opposite bets. Archetype-constrained fitting wins; UniRig (MIT) is the general-mesh assist.",
    status: "real",
    gate: "weights · influence cap · joints inside volume",
  },
  {
    n: 6,
    title: "Animation",
    io: "rig → 7 clips, all in-place",
    body: "Non-humanoid procedural gait synthesis with the planted-foot world-space solver: per leg per key, bisect the lift joint so the lowest skinned vertex lands on the ground plane.",
    correction:
      "Motion-diffusion models output humanoid SMPL skeletons and won't animate a spider at all. The retarget stage they require is never mentioned in the original; non-humanoids need procedural synthesis.",
    status: "real",
    gate: "owned by Stage 8",
  },
  {
    n: 7,
    title: "Packaging",
    io: "→ GLB + 2 sidecars",
    body: "Hand-written glTF 2.0 writer emits the GLB, asset_spec.json (what was asked) and godot_setup.json (the engine contract: collision, hitboxes, state machine, speeds).",
    correction:
      "Treating hitbox timing as sidecar data rather than engine-side hand-tuning is the original's best idea — kept and extended into a full machine-readable contract.",
    status: "real",
    gate: "Khronos glTF validator: zero errors, zero warnings",
  },
  {
    n: 8,
    title: "Validation & write-back",
    io: "GLB → report + measured speeds",
    body: "An independent reader re-parses the GLB, runs CPU forward-kinematics + linear-blend skinning, checks ten properties, then measures locomotion speed and writes it back into the contract.",
    correction:
      "The single biggest addition over the original: a closed loop. The engine consumes measured truth, not authored intent. Any failure loops to the owning stage with a perturbed seed.",
    status: "real",
    gate: "10/10 semantic checks + Khronos merged",
  },
];

export type LicenseRow = {
  component: string;
  role: string;
  license: string;
  catch: string;
  ok: boolean;
};

export const licenseTable: LicenseRow[] = [
  { component: "TRELLIS / TRELLIS.2 (Microsoft)", role: "image/text → 3D", license: "MIT (code + weights)", catch: "none — strongest open option, omitted by the original", ok: true },
  { component: "UniRig (Tsinghua / VAST)", role: "auto-rigging", license: "MIT", catch: "released checkpoint is the Articulation-XL2.0 variant", ok: true },
  { component: "Hunyuan3D 2.0 / 2.1 (Tencent)", role: "image → 3D", license: "Tencent community", catch: "territory-excluded: EU, UK, South Korea", ok: false },
  { component: "Stable Fast 3D (Stability)", role: "image → 3D", license: "Stability community", catch: "free under US$1M revenue, attribution required", ok: false },
  { component: "TripoSR", role: "image → 3D", license: "MIT", catch: "quality well behind TRELLIS-class models", ok: true },
  { component: "FLUX.1-schnell / dev", role: "concept image", license: "Apache-2.0 / non-commercial", catch: "use schnell for commercial work, not dev", ok: true },
  { component: "Kimodo (NVIDIA, 2026)", role: "motion diffusion", license: "Apache-2.0", catch: "humanoid skeleton families only — no non-humanoids", ok: false },
  { component: "Instant Meshes / QuadriFlow", role: "retopo", license: "open source", catch: "none", ok: true },
  { component: "Godot 4", role: "engine", license: "MIT", catch: "none", ok: true },
];

export type HardwareRow = { stage: string; vram: string; note: string };

export const hardwareTable: HardwareRow[] = [
  { stage: "FLUX.1 concept image", vram: "12–24 GB", note: "schnell variant, quantized fits lower" },
  { stage: "TRELLIS.2 mesh gen", vram: "~16–24 GB", note: "4B params; 24 GB consumer card is the target" },
  { stage: "Hunyuan3D 2.x", vram: "~10–16 GB", note: "where licensable" },
  { stage: "Kimodo motion", vram: "~17 GB", note: "humanoids only" },
  { stage: "Retopo / rig / animate / package / validate", vram: "CPU", note: "the entire POC ran with no GPU at all" },
];

export const limitations: string[] = [
  "The ML stages (concept image, image-to-3D) are stubbed; their I/O contracts are defined so TRELLIS.2 + retopo can slot in where the procedural generator now sits.",
  "The GDScript is carefully written but unverified in-engine — treat it as a strong first draft.",
  "One archetype (arachnid) is implemented. The per-archetype template approach is the point, but each new archetype is real work.",
  "Skinning is rigid (1 bone per vertex) — correct for PS1, insufficient for smooth organic deformation.",
  "Materials are vertex colors only; the PS1 look is completed shader-side in Godot (affine warp, dither, fog).",
];

/** The clip dock, in narrative order, with roles pulled from the contract. */
export const clipOrder = [
  { name: "idle-loop", label: "idle", kind: "loop" },
  { name: "walk-loop", label: "walk", kind: "loop" },
  { name: "run-loop", label: "run", kind: "loop" },
  { name: "attack_01", label: "slam", kind: "attack" },
  { name: "attack_02", label: "bite", kind: "attack" },
  { name: "hit", label: "hit", kind: "react" },
  { name: "death", label: "death", kind: "terminal" },
] as const;

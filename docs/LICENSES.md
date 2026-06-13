# Licenses (verified at build time)

The "free pipeline" claim must hold worldwide. MIT/Apache components are chosen
first; region- or revenue-restricted models stay opt-in, flagged, and warned.
Re-verify before relying on any entry — the AMD/ROCm stack moves fast.

| Component | Role | License | Worldwide-free? | Catch |
|-----------|------|---------|:---------------:|-------|
| **TRELLIS / TRELLIS.2** (Microsoft) | Stage 3 mesh gen | MIT (code + weights) | ✅ | Preferred default. AMD: custom exts (`o_voxel`, `cumesh`, `flexgemm`) + `nvdiffrast` need a HIP source build for gfx1151. |
| **UniRig** (VAST / Tsinghua) | Stage 5 auto-rig assist | MIT | ✅ | Verify no CUDA-only custom ops before relying on ROCm. |
| **FLUX.1-schnell** (Black Forest Labs) | Stage 2 concept image | Apache-2.0 | ✅ | Use **schnell**, NOT flux-dev (non-commercial). |
| **Kimodo** (NVIDIA nv-tlabs) | humanoid motion | Apache-2.0 | ✅ | Humanoid skeletons only (SMPL-X/SOMA/Unitree G1). Non-humanoids use Stage-6 procedural. |
| **Instant Meshes / QuadriFlow** | Stage 4 retopo | open source (CPU) | ✅ | None. |
| **Blender** | Stage 4 bake/decimate/UV | GPL | ✅ | Headless; HIP Cycles on AMD or CPU fallback. |
| **Khronos `gltf-validator`** | Stage 7 conformance | Apache-2.0 | ✅ | via npm. |
| **Godot 4.3+** | engine | MIT | ✅ | Vulkan on AMD. |
| Hunyuan3D 2.x (Tencent) | Stage 3 alt | Tencent community | ❌ | **Excludes EU, UK, South Korea.** Opt-in + region warning only. |
| Stable Fast 3D (Stability) | Stage 3 alt | Stability community | ❌ | Free only under US$1M annual revenue + attribution. Opt-in. |
| TripoSR | Stage 3 alt | MIT | ✅ | Quality well behind TRELLIS-class; not default. |

Default shipping set is entirely MIT/Apache/GPL/open and worldwide-free. The
restricted models above are never reached unless explicitly opted into.

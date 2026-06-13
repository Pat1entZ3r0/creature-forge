"""
Stage 3 (live tier) — TRELLIS.2 image/text -> textured mesh on ROCm/gfx1151.

MIT (code + weights), the strongest open option. This is the real work on this
hardware: the custom extensions (o_voxel, cumesh, flexgemm) and nvdiffrast have no
CUDA-binary drop-in and must be built FROM SOURCE for gfx1151:

    PYTORCH_ROCM_ARCH=gfx1151 FORCE_CUDA=1 CUDA_HOME=/opt/rocm ROCM_HOME=/opt/rocm \
        pip install . --no-build-isolation     # per extension

Use nvdiffrast's OpenGL backend (no HIP rasterizer exists) with the EGL/Xvfb GL
context from preflight, and the xformers/pytorch attention backend (flash-attn is
unavailable). Expect minutes per generation; the 128 GB pool means no quantization.

If any extension's gfx1151 rebuild fails, record the exact error in
docs/HARDWARE.md, keep Stage 3 on the procedural fallback, and move on — the
orchestrator does this automatically by catching GpuUnavailable.

Output: a RawMesh (triangle soup + albedo). Stage 4 retopologizes it; Stage 5 fits
the template skeleton. AMD-target-only; not executable on this Windows box.
"""

from __future__ import annotations

import os

from pipeline.gpu.availability import GpuUnavailable, RawMesh, require_gpu


def generate_mesh(spec: dict, concept_image=None) -> RawMesh:
    pf = require_gpu("Stage 3 TRELLIS.2")
    os.environ.setdefault("ATTN_BACKEND", pf.get("attention_backend", "xformers"))
    # nvdiffrast OpenGL backend needs the GL context the preflight stood up
    if not pf.get("gl_context", {}).get("pass"):
        raise GpuUnavailable("Stage 3: no offscreen GL context (nvdiffrast OpenGL backend); "
                             "see docs/HARDWARE.md")
    try:
        import numpy as np  # noqa: F401
        import torch  # noqa: F401
        from trellis.pipelines import TrellisImageTo3DPipeline, TrellisTextTo3DPipeline
    except ImportError as e:  # noqa: BLE001
        raise GpuUnavailable(
            f"Stage 3: TRELLIS.2 not importable ({e}). Build the gfx1151 extensions "
            "(o_voxel/cumesh/flexgemm/nvdiffrast) from source — see this module's header."
        )

    seed = int(spec["seed"])
    if concept_image is not None:
        pipe = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large").to("cuda")
        outputs = pipe.run(concept_image, seed=seed)
    else:
        pipe = TrellisTextTo3DPipeline.from_pretrained("microsoft/TRELLIS-text-large").to("cuda")
        outputs = pipe.run(spec["prompt"], seed=seed)

    mesh = outputs["mesh"][0]
    verts = mesh.vertices.detach().cpu().numpy()
    faces = mesh.faces.detach().cpu().numpy()
    return RawMesh(verts=verts, faces=faces, albedo=outputs.get("texture"),
                   meta={"source": "trellis2", "seed": seed})

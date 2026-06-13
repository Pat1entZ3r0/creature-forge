"""
Stage 2 (optional) — concept image via FLUX.1-schnell on ROCm.

Apache-2.0 (schnell, NOT flux-dev). Runs through diffusers on the gfx1151 torch
wheel; the 128 GB unified pool makes it comfortable. Skipped entirely when Stage 3
runs from text. AMD-target-only — see docs/HARDWARE.md.

NOTE: written against the diffusers API for the target; it is exercised only on
the AMD box (this build machine has no ROCm). It never fabricates an image: if the
GPU/deps are absent it raises GpuUnavailable and the caller skips concept art.
"""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.gpu.availability import GpuUnavailable, require_gpu


def generate_concept(spec: dict, out_dir: Path) -> Path:
    pf = require_gpu("Stage 2 FLUX.1-schnell")
    os.environ.setdefault("ATTN_BACKEND", pf.get("attention_backend", "xformers"))
    try:
        import torch
        from diffusers import FluxPipeline
    except ImportError as e:  # noqa: BLE001
        raise GpuUnavailable(f"Stage 2: diffusers/torch unavailable ({e})")

    prompt = f"{spec['prompt']}, {spec['style']}, single hero reference, neutral background"
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16
    ).to("cuda")
    # schnell is a few-step model; seed pinned for determinism
    gen = torch.Generator(device="cuda").manual_seed(int(spec["seed"]))
    image = pipe(prompt, num_inference_steps=4, guidance_scale=0.0, generator=gen).images[0]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec.get('archetype', 'asset')}_concept.png"
    image.save(path)
    return path

"""
pipeline/build.py — wires the CPU stages into a deterministic asset build.

  Stage 5 (rig)   archetype.build_skeleton()  -> template skeleton (fit = template
                                                  for the procedural tier)
  Stage 3 (mesh)  archetype.build_mesh(sk)    -> procedural fallback geometry,
                                                  rigidly bound to the template
  Stage 6 (anim)  archetype.build_clips(sk, solver) -> 7 clips, ground-solved
  Stage 7 (pack)  write_glb + both sidecars

The generative Stage-3 tier (TRELLIS.2, Milestone 4, AMD-only) swaps into the
same socket: it returns a Mesh, and Stage 5 then fits the template to it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.glb import write_glb
from pipeline.registry import get_archetype
from pipeline.solver import PlantedFootSolver


def _generative(spec: dict, arch):
    """Stage 2/3/4/5 generative path (TRELLIS.2). Raises GpuUnavailable off-target."""
    from pipeline.gpu.stage3_trellis import generate_mesh
    from pipeline.gpu.stage4_finish import finish
    from pipeline.gpu.stage5_fit import fit_template

    raw = generate_mesh(spec)            # Stage 3: TRELLIS.2 -> raw textured mesh
    finished = finish(raw, spec)         # Stage 4: retopo/decimate/UV/bake
    return fit_template(finished, arch, spec)  # Stage 5: template fit + rigid skin


def build_asset(spec: dict, out_dir: Path, mesh_tier: str = "procedural") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arch = get_archetype(spec["archetype"])
    stem = arch.model_stem
    fallback_reason = None
    tier_used = mesh_tier

    if mesh_tier == "trellis":
        from pipeline.gpu.availability import GpuUnavailable

        try:
            sk, mesh = _generative(spec, arch)  # Stages 3->4->5
        except GpuUnavailable as e:
            fallback_reason = str(e)
            tier_used = "procedural"
    if tier_used != "trellis":
        sk = arch.build_skeleton()              # Stage 5: template skeleton
        mesh = arch.build_mesh(sk)              # Stage 3: procedural fallback tier

    solver = PlantedFootSolver(sk, mesh, arch.legs(), arch.leg_rot)
    clips = arch.build_clips(sk, solver)        # Stage 6: ground-solved animation

    glb_path = out_dir / f"{stem}.glb"
    generator = f"creature-forge v0.1 ({arch.name} archetype, mesh_tier={tier_used})"
    total, tris, verts = write_glb(glb_path, sk, mesh, clips, generator)  # Stage 7

    setup = arch.godot_setup(sk, mesh, f"{stem}.glb")
    (out_dir / f"{stem}.godot_setup.json").write_text(json.dumps(setup, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.asset_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    info = {
        "glb": glb_path, "stem": stem, "archetype": arch.name, "mesh_tier": tier_used,
        "bytes": total, "triangles": tris, "vertices": verts, "joints": len(sk.names),
        "clips": list(clips),
    }
    if fallback_reason:
        info["fallback_reason"] = fallback_reason
    return info

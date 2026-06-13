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


def build_asset(spec: dict, out_dir: Path, mesh_tier: str = "procedural") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arch = get_archetype(spec["archetype"])
    stem = arch.model_stem

    sk = arch.build_skeleton()                 # Stage 5: template skeleton
    mesh = arch.build_mesh(sk)                 # Stage 3: procedural fallback tier
    solver = PlantedFootSolver(sk, mesh, arch.legs(), arch.leg_rot)
    clips = arch.build_clips(sk, solver)       # Stage 6: ground-solved animation

    glb_path = out_dir / f"{stem}.glb"
    generator = f"creature-forge v0.1 ({arch.name} archetype, mesh_tier={mesh_tier})"
    total, tris, verts = write_glb(glb_path, sk, mesh, clips, generator)  # Stage 7

    setup = arch.godot_setup(sk, mesh, f"{stem}.glb")
    (out_dir / f"{stem}.godot_setup.json").write_text(json.dumps(setup, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.asset_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    return {
        "glb": glb_path, "stem": stem, "archetype": arch.name, "mesh_tier": mesh_tier,
        "bytes": total, "triangles": tris, "vertices": verts, "joints": len(sk.names),
        "clips": list(clips),
    }

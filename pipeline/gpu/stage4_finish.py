"""
Stage 4 — game-asset finishing for the generative path.

retopo (Instant Meshes / QuadriFlow, CPU) -> decimate to tri_budget -> UV unwrap ->
bake albedo from the dense TRELLIS source onto the retopo mesh (Blender headless;
HIP Cycles if available, else CPU — 16 Zen 5 cores). No LOD authoring (Godot 4
auto-LODs at import). PS1 shader work (affine warp, vertex snap, dither, fog) stays
a single shared Godot material, NOT baked into the asset.

These are CPU tools but only relevant when Stage 3 ran. Missing binaries raise
GpuUnavailable so the orchestrator falls back to the procedural tier and logs it.
Verified only on the target; this build box has neither Blender nor Instant Meshes.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.gpu.availability import GpuUnavailable, RawMesh

ROOT = Path(__file__).resolve().parent.parent.parent


def _tool(*names: str) -> str:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    raise GpuUnavailable(f"Stage 4: none of {names} found on PATH (retopo/bake). "
                         "Install Instant Meshes / Blender or use the procedural tier.")


def finish(raw: RawMesh, spec: dict) -> RawMesh:
    retopo = _tool("Instant Meshes", "instant-meshes", "InstantMeshes")
    blender = _tool("blender")
    work = Path(tempfile.mkdtemp(prefix="cf_finish_"))
    dense = work / "dense.obj"
    retopo_out = work / "retopo.obj"
    final = work / "final.glb"

    _write_obj(dense, raw)
    # 1) retopo to a quad-dominant mesh at roughly the target face count
    subprocess.run([retopo, str(dense), "-o", str(retopo_out),
                    "-f", str(spec["tri_budget"] // 2)], check=True)
    # 2) decimate to tri_budget + UV unwrap + bake albedo from the dense source
    bake_script = ROOT / "pipeline" / "gpu" / "blender_bake.py"
    subprocess.run([blender, "--background", "--python", str(bake_script), "--",
                    str(dense), str(retopo_out), str(final),
                    str(spec["tri_budget"]), str(spec.get("texture_budget_px") or 256)],
                   check=True)
    return RawMesh(verts=raw.verts, faces=raw.faces, albedo=str(final),
                   meta={**raw.meta, "finished_glb": str(final), "retopo": str(retopo_out)})


def _write_obj(path: Path, raw: RawMesh) -> None:
    lines = [f"v {x} {y} {z}" for x, y, z in raw.verts]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in raw.faces]
    path.write_text("\n".join(lines), encoding="utf-8")

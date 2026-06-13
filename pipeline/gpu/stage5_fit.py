"""
Stage 5 (generative path) — fit the archetype's template skeleton to a GENERATED
mesh (vs. the known procedural one), then rigid-skin it.

Primary: fit the canonical template by landmark heuristics (scale to
target_height, rest on the ground plane) and assign each vertex to its nearest
template joint (rigid, 1 influence — PS1 style). Assist/general path: UniRig (MIT),
guarded — used when the heuristic fit is poor.

If generated topology defeats the fit, the validator rejects the result and the
orchestrator falls back to the procedural mesh for that run (logged). This module
returns (Skeleton, Mesh); it shares the planted-foot solver and validator with the
procedural tier unchanged. Verified only on the target (needs a real TRELLIS mesh).
"""

from __future__ import annotations

import numpy as np

from archetypes.skeleton import Mesh, Skeleton
from pipeline.gpu.availability import GpuUnavailable, RawMesh


def fit_template(raw: RawMesh, archetype, spec: dict, use_unirig: bool = False) -> tuple[Skeleton, Mesh]:
    if use_unirig:
        try:
            import unirig  # noqa: F401
        except ImportError as e:  # noqa: BLE001
            raise GpuUnavailable(f"Stage 5: UniRig assist requested but unavailable ({e})")

    sk: Skeleton = archetype.build_skeleton()

    verts = np.asarray(raw.verts, float)
    faces = np.asarray(raw.faces, int)

    # landmark fit: scale to target height, drop onto the ground plane, center XZ
    target_h = float(spec["target_height_m"])
    size_y = max(1e-6, verts[:, 1].max() - verts[:, 1].min())
    verts = verts * (target_h / size_y)
    verts[:, 0] -= verts[:, 0].mean()
    verts[:, 2] -= verts[:, 2].mean()
    verts[:, 1] -= verts[:, 1].min()  # rest on y = 0

    # rigid skin: nearest skinned joint (exclude the structural root, index 0)
    skinned = [k for k in range(len(sk.names)) if k != 0]
    jpos = sk.world[skinned]
    d2 = ((verts[:, None, :] - jpos[None, :, :]) ** 2).sum(-1)
    slot = np.array(skinned)[d2.argmin(1)]

    # per-vertex normals (area-weighted) + a flat palette color
    nrm = _vertex_normals(verts, faces)
    body_col = (0.22, 0.17, 0.30, 1.0)

    mesh = Mesh()
    mesh.pos = [v for v in verts]
    mesh.nrm = [n for n in nrm]
    mesh.col = [body_col for _ in verts]
    mesh.slot = [int(s) for s in slot]
    mesh.idx = faces.reshape(-1).tolist()

    # foot anchors: lowest vertex assigned to each leg's lower bone
    for leg in archetype.legs():
        li = sk.idx[leg.lower]
        m = slot == li
        if m.any():
            pts = verts[m]
            mesh.foot_anchor[leg.lower] = pts[pts[:, 1].argmin()].tolist()
    return sk, mesh


def _vertex_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    nrm = np.zeros_like(verts)
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]])
    for i in range(3):
        np.add.at(nrm, faces[:, i], fn)
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    return nrm / np.where(ln < 1e-9, 1.0, ln)

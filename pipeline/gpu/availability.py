"""
GPU-stage availability guard.

The generative stages (2 FLUX, 3 TRELLIS.2) only run on the AMD/ROCm target with
a GREEN Milestone-0.5 preflight. Everywhere else they raise GpuUnavailable and the
orchestrator falls back to the deterministic procedural Stage-3 tier. This is the
sanctioned, honestly-recorded state — never a faked stage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
PREFLIGHT = ROOT / "out" / "preflight.json"


class GpuUnavailable(RuntimeError):
    """Raised when a GPU stage is invoked without a green preflight / required deps."""


def preflight() -> dict:
    if PREFLIGHT.exists():
        try:
            return json.loads(PREFLIGHT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def gpu_enabled() -> bool:
    return bool(preflight().get("gpu_enabled"))


def require_gpu(stage: str) -> dict:
    pf = preflight()
    if not pf.get("gpu_enabled"):
        reason = pf.get("reason") or "run `python scripts/preflight.py` on the AMD/ROCm target first"
        raise GpuUnavailable(f"{stage}: GPU disabled (preflight gpu_enabled=false - {reason})")
    return pf


@dataclass
class RawMesh:
    """Generative-stage output before retopo/rig: a triangle soup + optional albedo.
    Stage 4 retopologizes/decimates it; Stage 5 fits the template skeleton to it."""

    verts: np.ndarray  # (V, 3)
    faces: np.ndarray  # (F, 3) int
    albedo: object = None  # PIL.Image or texture path, optional
    meta: dict = field(default_factory=dict)

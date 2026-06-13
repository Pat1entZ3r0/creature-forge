"""
conventions.py — the non-negotiable global conventions, in one place.

Every stage imports its constants from here, and the validator asserts the
produced artifact obeys them. These exist because violating any one of them
makes an asset silently wrong in-engine (a spider imported at 100x scale,
facing +Z, sliding on its feet, or punching through the floor).

Units: meters. Up: +Y. Forward: -Z (Godot convention; no rotation on import).
Quaternions: glTF order (x, y, z, w).
Skeleton: identity bind rotations, translation-only bones.
Skinning: rigid (1 influence) for PS1; otherwise <=4, weights normalized.
Locomotion: in-place. World movement is the controller's job.
"""

from __future__ import annotations

import numpy as np

# ── coordinate system ───────────────────────────────────────────────────────
# UNITS is the literal stored in the asset_spec (meters, abbreviated "m").
UNITS = "m"
UP_AXIS = "+Y"
FORWARD_AXIS = "-Z"
QUATERNION_ORDER = "xyzw"  # glTF

# ── skinning ────────────────────────────────────────────────────────────────
RIGID_MAX_INFLUENCES = 1  # PS1 style
GENERAL_MAX_INFLUENCES = 4
WEIGHT_NORM_TOL = 1e-5

# ── validator limits (Stage 8 gate; see validation/validator.py) ─────────────
FOOT_CONTACT_LIMIT_MM = 8.0  # worst planted-foot world-Y deviation
GROUND_PENETRATION_LIMIT_M = -0.005  # no skinned vertex below this, anywhere
DEATH_COLLAPSE_MAX_Y = 0.26  # death clip must drop the body below this
LOOP_CLOSURE_TOL = 1e-6  # first key == last key on -loop clips
IN_PLACE_DRIFT_TOL = 1e-4  # root/body XZ drift over a cycle
STRESS_SAMPLES_PER_CLIP = 64  # dense ground-penetration sweep density

# ── solver ──────────────────────────────────────────────────────────────────
# The planted-foot solver digs each stance foot 2.5 mm into the ground — well
# inside the -5 mm penetration limit, and below the 8 mm contact tolerance.
GROUND_TARGET = -0.0025
SOLVER_BISECT_ITERS = 44
SOLVER_LIFT_RANGE = (-40.0, 82.0)  # degrees searched for the planted lift angle

# ── glTF component-type / accessor enums (shared by writer and reader) ────────
GLTF_BYTE = 5120
GLTF_UBYTE = 5121
GLTF_SHORT = 5122
GLTF_USHORT = 5123
GLTF_UINT = 5125
GLTF_FLOAT = 5126
GLTF_ARRAY_BUFFER = 34962
GLTF_ELEMENT_ARRAY_BUFFER = 34963
GLTF_MAGIC = 0x46546C67
GLTF_CHUNK_JSON = 0x4E4F534A
GLTF_CHUNK_BIN = 0x004E4942

COMPONENT_DTYPE = {
    GLTF_BYTE: np.int8,
    GLTF_UBYTE: np.uint8,
    GLTF_SHORT: np.int16,
    GLTF_USHORT: np.uint16,
    GLTF_UINT: np.uint32,
    GLTF_FLOAT: np.float32,
}
TYPE_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# ── quaternion / rotation math kit ───────────────────────────────────────────
Q_ID = np.array([0.0, 0.0, 0.0, 1.0])  # identity quaternion (xyzw)


def q_axis(axis, deg: float) -> np.ndarray:
    """Quaternion (xyzw) from an axis and an angle in degrees."""
    a = np.asarray(axis, dtype=np.float64)
    a = a / np.linalg.norm(a)
    h = np.radians(deg) * 0.5
    s = np.sin(h)
    return np.array([a[0] * s, a[1] * s, a[2] * s, np.cos(h)], dtype=np.float64)


def q_mul(qa, qb) -> np.ndarray:
    """Hamilton product, xyzw storage. R(q_mul(a,b)) = R(a) @ R(b): b applies first."""
    ax, ay, az, aw = qa
    bx, by, bz, bw = qb
    return np.array([
        aw * bx + bw * ax + (ay * bz - az * by),
        aw * by + bw * ay + (az * bx - ax * bz),
        aw * bz + bw * az + (ax * by - ay * bx),
        aw * bw - (ax * bx + ay * by + az * bz),
    ])


def q_mat(q) -> np.ndarray:
    """3x3 rotation matrix from a quaternion (xyzw)."""
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def bell(t):
    """Smooth 0->1->0 hump over t in [0,1] (sin arch)."""
    return np.sin(np.pi * np.clip(t, 0.0, 1.0))


# ── convention assertions (called by the validator) ──────────────────────────
class ConventionError(AssertionError):
    pass


def assert_spec_conventions(spec: dict) -> None:
    """Raise ConventionError if a compiled asset_spec violates the globals."""
    if spec.get("units") != UNITS:
        raise ConventionError(f"units must be {UNITS!r}, got {spec.get('units')!r}")
    if spec.get("up") != UP_AXIS:
        raise ConventionError(f"up must be {UP_AXIS!r}, got {spec.get('up')!r}")
    if spec.get("forward") != FORWARD_AXIS:
        raise ConventionError(f"forward must be {FORWARD_AXIS!r}, got {spec.get('forward')!r}")
    if not spec.get("locomotion", {}).get("in_place", False):
        raise ConventionError("locomotion.in_place must be true (clips never translate the root)")

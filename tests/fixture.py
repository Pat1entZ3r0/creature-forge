"""
tests/fixture.py — tiny hand-made skinned GLBs for the Milestone-1 validator gate.

This is TEST code with its own minimal glTF writer; it deliberately shares NO
code with the pipeline (which doesn't exist yet at M1). It builds:
  * a GOOD fixture that passes all validator checks, and
  * a BROKEN fixture identical except the death clip punches a foot 6 cm through
    the floor (must FAIL ground-penetration).

Rig: root (structural) -> body -> leg. Two flat-shaded boxes, rigid-skinned.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "out" / "fixtures"

Q_ID = [0.0, 0.0, 0.0, 1.0]


# ── minimal GLB writer ───────────────────────────────────────────────────────
class _GLB:
    def __init__(self):
        self.blob = bytearray()
        self.views: list = []
        self.accessors: list = []

    def _push(self, data, target=None):
        while len(self.blob) % 4:
            self.blob.append(0)
        off = len(self.blob)
        self.blob += data
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            v["target"] = target
        self.views.append(v)
        return len(self.views) - 1

    def acc(self, arr, ctype, atype, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        view = self._push(arr.tobytes(), target)
        a = {"bufferView": view, "componentType": ctype, "count": arr.shape[0], "type": atype}
        if minmax:
            flat = arr.reshape(arr.shape[0], -1)
            a["min"] = [float(x) for x in flat.min(0)]
            a["max"] = [float(x) for x in flat.max(0)]
        self.accessors.append(a)
        return len(self.accessors) - 1


def _box(center, size, color, slot):
    """Axis-aligned flat-shaded box -> (pos, nrm, col, jnt, idx-local)."""
    c = np.asarray(center, float)
    h = np.asarray(size, float) / 2
    corners = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * h + c
    faces = [
        (0, 1, 3, 2, (-1, 0, 0)), (4, 6, 7, 5, (1, 0, 0)),
        (0, 4, 5, 1, (0, -1, 0)), (2, 3, 7, 6, (0, 1, 0)),
        (0, 2, 6, 4, (0, 0, -1)), (1, 5, 7, 3, (0, 0, 1)),
    ]
    pos, nrm, col, jnt, idx = [], [], [], [], []
    for a, b, cc, d, n in faces:
        base = len(pos)
        for vi in (a, b, cc, d):
            pos.append(corners[vi]); nrm.append(n); col.append((*color, 1.0)); jnt.append(slot)
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    return pos, nrm, col, jnt, idx


def write_glb(path: Path, bones, boxes, clips):
    """bones: [(name, parent_idx, world_xyz)]; boxes: [(center,size,color,slot)];
    clips: {name: {"len": T, "rot": {bone:[(t,quat)]}, "trs": {bone:[(t,vec3)]}}}."""
    names = [b[0] for b in bones]
    idx_of = {n: i for i, n in enumerate(names)}
    parents = [b[1] for b in bones]
    world = np.array([b[2] for b in bones], float)

    pos, nrm, col, jnt, tri = [], [], [], [], []
    for center, size, color, slot in boxes:
        p, nm, c, j, ix = _box(center, size, color, slot)
        base = len(pos)
        pos += p; nrm += nm; col += c; jnt += j
        tri += [base + k for k in ix]

    g = _GLB()
    P = np.asarray(pos, np.float32)
    N = np.asarray(nrm, np.float32)
    C = np.asarray(col, np.float32)
    J = np.zeros((len(jnt), 4), np.uint16); J[:, 0] = jnt
    W = np.zeros((len(jnt), 4), np.float32); W[:, 0] = 1.0
    I = np.asarray(tri, np.uint32)

    a_pos = g.acc(P, 5126, "VEC3", 34962, minmax=True)
    a_nrm = g.acc(N, 5126, "VEC3", 34962)
    a_col = g.acc(C, 5126, "VEC4", 34962)
    a_jnt = g.acc(J, 5123, "VEC4", 34962)
    a_wgt = g.acc(W, 5126, "VEC4", 34962)
    a_idx = g.acc(I, 5125, "SCALAR", 34963)

    nodes, children = [], {k: [] for k in range(len(names))}
    for k, (name, parent, _) in enumerate(bones):
        local = world[k] - (world[parent] if parent >= 0 else 0.0)
        nodes.append({"name": name, "translation": [float(x) for x in local]})
        if parent >= 0:
            children[parent].append(k)
    for k, ch in children.items():
        if ch:
            nodes[k]["children"] = ch

    ibm = np.zeros((len(names), 16), np.float32)
    for k in range(len(names)):
        m = np.identity(4)
        m[3, 0:3] = -world[k]
        ibm[k] = m.reshape(-1)
    a_ibm = g.acc(ibm, 5126, "MAT4")

    mesh_node = len(nodes)
    nodes.append({"name": "FixtureMesh", "mesh": 0, "skin": 0})

    animations = []
    for name, clip in clips.items():
        samplers, channels = [], []

        def add(bone, path, keys, comp):
            times = np.asarray([k[0] for k in keys], np.float32).reshape(-1, 1)
            vals = np.asarray([k[1] for k in keys], np.float32)
            a_t = g.acc(times, 5126, "SCALAR", minmax=True)
            a_v = g.acc(vals, 5126, comp)
            samplers.append({"input": a_t, "output": a_v, "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": idx_of[bone], "path": path}})

        for bone, keys in sorted(clip.get("rot", {}).items()):
            add(bone, "rotation", keys, "VEC4")
        for bone, keys in sorted(clip.get("trs", {}).items()):
            add(bone, "translation", keys, "VEC3")
        animations.append({"name": name, "samplers": samplers, "channels": channels})

    gltf = {
        "asset": {"version": "2.0", "generator": "creature-forge fixture"},
        "scene": 0,
        "scenes": [{"nodes": [idx_of[names[0]], mesh_node], "name": "fixture"}],
        "nodes": nodes,
        "skins": [{"skeleton": 0, "joints": list(range(len(names))), "inverseBindMatrices": a_ibm}],
        "meshes": [{"name": "fixture_mesh", "primitives": [{
            "attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "COLOR_0": a_col,
                           "JOINTS_0": a_jnt, "WEIGHTS_0": a_wgt},
            "indices": a_idx, "material": 0, "mode": 4}]}],
        "materials": [{"name": "flat", "doubleSided": False,
                       "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1],
                                                "metallicFactor": 0.0, "roughnessFactor": 0.95}}],
        "animations": animations,
        "buffers": [{"byteLength": len(g.blob)}],
        "bufferViews": g.views,
        "accessors": g.accessors,
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    bin_ = bytes(g.blob)
    while len(bin_) % 4:
        bin_ += b"\x00"
    total = 12 + 8 + len(js) + 8 + len(bin_)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942)); f.write(bin_)


# ── the two fixtures ─────────────────────────────────────────────────────────
BONES = [
    ("root", -1, (0.0, 0.0, 0.0)),
    ("body", 0, (0.0, 0.12, 0.0)),
    ("leg", 1, (0.12, 0.12, 0.0)),
]
BOXES = [
    ((0.0, 0.15, 0.0), (0.20, 0.18, 0.20), (0.25, 0.18, 0.30), 1),   # body -> slot 1
    ((0.12, 0.07, 0.0), (0.05, 0.14, 0.05), (0.16, 0.12, 0.22), 2),  # leg  -> slot 2
]
FOOT_ANCHOR = {"leg": [0.12, 0.0, 0.0]}


# bind-pose LOCAL translations (world(child) - world(parent))
BODY_LOCAL = [0.0, 0.12, 0.0]
LEG_LOCAL = [0.12, 0.0, 0.0]


def _const_clip(T, lower_leg=0.0):
    """All controlled bones keyed at their bind pose, first == last. Optionally
    lower the leg bone by `lower_leg` over the clip (used to break the floor)."""
    rot = {b: [(0.0, Q_ID), (T, Q_ID)] for b in ("body", "leg")}
    leg_end = [LEG_LOCAL[0], LEG_LOCAL[1] - lower_leg, LEG_LOCAL[2]]
    trs = {
        "body": [(0.0, BODY_LOCAL), (T, BODY_LOCAL)],
        "leg": [(0.0, LEG_LOCAL), (T, leg_end)],
    }
    return {"len": T, "rot": rot, "trs": trs}


def _sidecars(stem: str):
    spec = {
        "spec_version": "0.1", "prompt": "validator fixture", "style": "fixture",
        "archetype": "arachnid", "seed": 0, "units": "m", "up": "+Y", "forward": "-Z",
        "target_height_m": 0.24, "tri_budget": 200, "vert_budget": 400,
        "texture_budget_px": None, "material_model": "vertex-color",
        "locomotion": {"in_place": True},
        "animations": ["idle-loop", "walk-loop", "run-loop", "death"],
    }
    setup = {
        "contract_version": "0.1", "model_file": f"{stem}.glb", "display_name": "Fixture",
        "scale": 1.0, "forward": "-Z", "health": 10,
        "collision": {"type": "capsule", "radius": 0.12, "height": 0.24, "offset": [0, 0.12, 0]},
        "hurtbox": {"type": "capsule", "radius": 0.10, "height": 0.20, "offset": [0, 0.12, 0]},
        "locomotion": {"in_place": True,
                       "walk": {"anim": "walk-loop", "speed_mps": 0.0},
                       "run": {"anim": "run-loop", "speed_mps": 0.0},
                       "turn_speed_dps": 300},
        "animations": [
            {"name": "idle-loop", "loop": True, "role": "idle"},
            {"name": "walk-loop", "loop": True, "role": "locomotion"},
            {"name": "run-loop", "loop": True, "role": "locomotion"},
            {"name": "death", "loop": False, "role": "death"},
        ],
        "hitboxes": [],
        "state_machine": {"start": "idle",
                          "states": {"idle": {"anim": "idle-loop"}, "walk": {"anim": "walk-loop"},
                                     "run": {"anim": "run-loop"}, "death": {"anim": "death"}},
                          "transitions": [["idle", "walk", 0.1], ["walk", "idle", 0.1],
                                          ["idle", "death", 0.05]]},
        "foot_anchors": FOOT_ANCHOR,
        "skeleton": {"names": [b[0] for b in BONES], "parents": [b[1] for b in BONES],
                     "rest_world": [list(b[2]) for b in BONES]},
    }
    return spec, setup


def build(stem: str, broken: bool = False) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    clips = {
        "idle-loop": _const_clip(1.0),
        "walk-loop": _const_clip(0.8),
        "run-loop": _const_clip(0.5),
        # broken: death lowers the foot 6 cm through the floor (-> penetration fail)
        "death": _const_clip(1.0, lower_leg=0.06 if broken else 0.0),
    }
    glb = OUT / f"{stem}.glb"
    write_glb(glb, BONES, BOXES, clips)
    spec, setup = _sidecars(stem)
    (OUT / f"{stem}.asset_spec.json").write_text(json.dumps(spec, indent=2))
    (OUT / f"{stem}.godot_setup.json").write_text(json.dumps(setup, indent=2))
    return glb


def build_all():
    return build("good", broken=False), build("broken", broken=True)


if __name__ == "__main__":
    good, broken = build_all()
    print("wrote", good, "and", broken)

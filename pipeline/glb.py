"""
pipeline/glb.py — Stage 7 GLB writer (hand-written glTF 2.0).

Deterministic and byte-stable: fixed float32 attributes, sorted channels,
compact separators, no timestamps. Generalized over any Skeleton + Mesh + clips.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

from archetypes.skeleton import Mesh, Skeleton
from conventions import (
    GLTF_ARRAY_BUFFER,
    GLTF_ELEMENT_ARRAY_BUFFER,
    GLTF_FLOAT,
    GLTF_UINT,
    GLTF_USHORT,
)


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


def write_glb(path: Path, sk: Skeleton, mesh: Mesh, clips: dict, generator: str) -> tuple[int, int, int]:
    g = _GLB()
    names, parents, world = sk.names, sk.parents, sk.world
    idx_of = sk.idx
    n_joints = len(names)

    pos = np.asarray(mesh.pos, np.float32)
    nrm = np.asarray(mesh.nrm, np.float32)
    col = np.asarray(mesh.col, np.float32)
    jnt = np.zeros((len(mesh.slot), 4), np.uint16)
    jnt[:, 0] = mesh.slot
    wgt = np.zeros((len(mesh.slot), 4), np.float32)
    wgt[:, 0] = 1.0
    idx = np.asarray(mesh.idx, np.uint32)

    a_pos = g.acc(pos, GLTF_FLOAT, "VEC3", GLTF_ARRAY_BUFFER, minmax=True)
    a_nrm = g.acc(nrm, GLTF_FLOAT, "VEC3", GLTF_ARRAY_BUFFER)
    a_col = g.acc(col, GLTF_FLOAT, "VEC4", GLTF_ARRAY_BUFFER)
    a_jnt = g.acc(jnt, GLTF_USHORT, "VEC4", GLTF_ARRAY_BUFFER)
    a_wgt = g.acc(wgt, GLTF_FLOAT, "VEC4", GLTF_ARRAY_BUFFER)
    a_idx = g.acc(idx, GLTF_UINT, "SCALAR", GLTF_ELEMENT_ARRAY_BUFFER)

    nodes = []
    children = {k: [] for k in range(n_joints)}
    for k, name in enumerate(names):
        p = parents[k]
        local = world[k] - (world[p] if p >= 0 else 0.0)
        nodes.append({"name": name, "translation": [float(x) for x in local]})
        if p >= 0:
            children[p].append(k)
    for k, ch in children.items():
        if ch:
            nodes[k]["children"] = ch

    ibm = np.zeros((n_joints, 16), np.float32)
    for k in range(n_joints):
        m = np.identity(4)
        m[3, 0:3] = -world[k]
        ibm[k] = m.reshape(-1)
    a_ibm = g.acc(ibm, GLTF_FLOAT, "MAT4")

    mesh_node = len(nodes)
    nodes.append({"name": "CreatureMesh", "mesh": 0, "skin": 0})

    animations = []
    for name, clip in clips.items():
        samplers, channels = [], []

        def add(bone, path, keys, comp):
            times = np.asarray([k[0] for k in keys], np.float32).reshape(-1, 1)
            vals = np.asarray([k[1] for k in keys], np.float32)
            a_t = g.acc(times, GLTF_FLOAT, "SCALAR", minmax=True)
            a_v = g.acc(vals, GLTF_FLOAT, comp)
            samplers.append({"input": a_t, "output": a_v, "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": idx_of[bone], "path": path}})

        for b, keys in sorted(clip["rot"].items()):
            add(b, "rotation", keys, "VEC4")
        for b, keys in sorted(clip["trs"].items()):
            add(b, "translation", keys, "VEC3")
        animations.append({"name": name, "samplers": samplers, "channels": channels})

    gltf = {
        "asset": {"version": "2.0", "generator": generator},
        "scene": 0,
        "scenes": [{"nodes": [idx_of[names[0]], mesh_node], "name": "creature"}],
        "nodes": nodes,
        "skins": [{"skeleton": idx_of[names[0]], "joints": list(range(n_joints)),
                   "inverseBindMatrices": a_ibm, "name": "CreatureSkin"}],
        "meshes": [{"name": "creature_lod0", "primitives": [{
            "attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "COLOR_0": a_col,
                           "JOINTS_0": a_jnt, "WEIGHTS_0": a_wgt},
            "indices": a_idx, "material": 0, "mode": 4}]}],
        "materials": [{"name": "creature_flat", "doubleSided": False,
                       "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1],
                                                "metallicFactor": 0.0, "roughnessFactor": 0.95}}],
        "animations": animations,
        "buffers": [{"byteLength": len(g.blob)}],
        "bufferViews": g.views,
        "accessors": g.accessors,
    }

    js = json.dumps(gltf, separators=(",", ":"), sort_keys=False).encode()
    while len(js) % 4:
        js += b" "
    bin_ = bytes(g.blob)
    while len(bin_) % 4:
        bin_ += b"\x00"
    total = 12 + 8 + len(js) + 8 + len(bin_)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942))
        f.write(bin_)
    return total, len(idx) // 3, len(pos)

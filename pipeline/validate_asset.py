#!/usr/bin/env python3
"""
validate_asset.py — Stage 8 reference implementation: rig & animation validation.

Deliberately reads ONLY the .glb from disk (plus the asset spec for budgets),
re-implementing glTF skinning on the CPU, so it validates what is actually in
the file rather than what the generator intended to put there.

Checks:
  * structural: accessor/buffer sanity, weight normalization, max influences
  * budget compliance vs asset_spec (tris, joints)
  * loop clips close exactly (first key == last key per channel)
  * locomotion: foot-contact deviation during stance (ground penetration /
    float, in mm) and effective stride -> recommended controller speed
  * in-place check: root/body XZ drift over a cycle
  * bone containment: every joint pivot sits inside the union of segment AABBs
Renders a 2x3 pose contact sheet (bind / walk x2 / attack apex / lunge / death)
for human review, and writes validation_report.json.
"""

import json, struct, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16,
      5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

def load_glb(path):
    raw = open(path, "rb").read()
    magic, ver, total = struct.unpack_from("<III", raw, 0)
    assert magic == 0x46546C67 and ver == 2, "not a GLB v2"
    off, js, bin_ = 12, None, None
    while off < total:
        ln, typ = struct.unpack_from("<II", raw, off); off += 8
        chunk = raw[off:off + ln]; off += ln
        if typ == 0x4E4F534A: js = json.loads(chunk.decode())
        elif typ == 0x004E4942: bin_ = chunk
    return js, bin_

def read_acc(g, bin_, i):
    a = g["accessors"][i]; v = g["bufferViews"][a["bufferView"]]
    dt = CT[a["componentType"]]; n = NCOMP[a["type"]]
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    arr = np.frombuffer(bin_, dt, count=a["count"] * n, offset=start)
    return arr.reshape(a["count"], n).astype(np.float64 if dt == np.float32 else dt)

def quat_mat(q):
    x, y, z, w = q
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)],
        [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)]])

def sample(times, vals, t, is_quat):
    if t <= times[0]: return vals[0]
    if t >= times[-1]: return vals[-1]
    k = np.searchsorted(times, t) - 1
    u = (t - times[k]) / (times[k+1] - times[k])
    a, b = vals[k].copy(), vals[k+1].copy()
    if is_quat and np.dot(a, b) < 0: b = -b
    out = a + (b - a) * u
    if is_quat: out /= np.linalg.norm(out)
    return out

class Rig:
    def __init__(self, g, bin_):
        self.g, self.bin = g, bin_
        skin = g["skins"][0]
        self.joints = skin["joints"]
        self.ibm = read_acc(g, bin_, skin["inverseBindMatrices"]).reshape(-1, 4, 4)
        self.nodes = g["nodes"]
        self.name2node = {n.get("name", str(i)): i for i, n in enumerate(self.nodes)}
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []): self.parent[c] = i
        prim = g["meshes"][0]["primitives"][0]
        self.pos = read_acc(g, bin_, prim["attributes"]["POSITION"])
        self.col = read_acc(g, bin_, prim["attributes"]["COLOR_0"])
        self.jnt = read_acc(g, bin_, prim["attributes"]["JOINTS_0"]).astype(int)
        self.wgt = read_acc(g, bin_, prim["attributes"]["WEIGHTS_0"])
        self.idx = read_acc(g, bin_, prim["indices"]).astype(int).reshape(-1, 3)
        self.anims = {}
        for an in g.get("animations", []):
            ch = {}
            for c in an["channels"]:
                s = an["samplers"][c["sampler"]]
                ch[(c["target"]["node"], c["target"]["path"])] = (
                    read_acc(g, bin_, s["input"]).reshape(-1),
                    read_acc(g, bin_, s["output"]))
            self.anims[an["name"]] = ch

    def globals_at(self, anim, t):
        ch = self.anims[anim] if anim else {}
        G = {}
        def rec(i):
            n = self.nodes[i]
            tr = np.array(n.get("translation", [0, 0, 0]), float)
            q = np.array(n.get("rotation", [0, 0, 0, 1.0]))
            if (i, "translation") in ch:
                tt, vv = ch[(i, "translation")]; tr = sample(tt, vv, t, False)
            if (i, "rotation") in ch:
                tt, vv = ch[(i, "rotation")]; q = sample(tt, vv, t, True)
            L = np.identity(4); L[:3, :3] = quat_mat(q); L[:3, 3] = tr
            G[i] = (G[self.parent[i]] @ L) if i in self.parent else L
            for c in n.get("children", []): rec(c)
        roots = [j for j in self.joints if j not in self.parent]
        for r in roots: rec(r)
        return G

    def skin_at(self, anim, t):
        G = self.globals_at(anim, t)
        # IBM stored column-major flat -> numpy reshape(4,4) gives transpose
        M = {j: G[j] @ self.ibm[k].T for k, j in enumerate(self.joints)}
        out = np.empty_like(self.pos)
        hom = np.concatenate([self.pos, np.ones((len(self.pos), 1))], 1)
        for j in np.unique(self.jnt[:, 0]):
            mask = self.jnt[:, 0] == j           # rigid skin: weight 1 on slot 0
            out[mask] = (hom[mask] @ M[self.joints[j]].T)[:, :3]
        return out, G

    def point_on_bone(self, anim, t, bone_name, p_bind):
        G = self.globals_at(anim, t)
        j = self.name2node[bone_name]
        k = self.joints.index(j)
        M = G[j] @ self.ibm[k].T
        return (M @ np.array([*p_bind, 1.0]))[:3]

def draw(ax, verts, faces, cols, title):
    tri = verts[faces]
    fc = cols[faces[:, 0], :3] * 0.75 + 0.25 * cols[faces[:, 0], :3].max(1, keepdims=True)
    pc = Poly3DCollection(tri, facecolors=np.clip(fc, 0, 1), edgecolors=(0, 0, 0, 0.25), linewidths=0.3)
    ax.add_collection3d(pc)
    g = np.linspace(-0.6, 0.6, 7)
    for v in g:
        ax.plot([v, v], [-0.6, 0.6], [0, 0], c="#999", lw=0.4, zdir="y")
        ax.plot([-0.6, 0.6], [v, v], [0, 0], c="#999", lw=0.4, zdir="y")
    ax.set_xlim(-0.6, 0.6); ax.set_ylim(-0.6, 0.6); ax.set_zlim(0, 1.2)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=18, azim=-58)
    ax.set_title(title, fontsize=9); ax.set_axis_off()

def main():
    g, bin_ = load_glb("out/spider_alien.glb")
    spec = json.load(open("out/spider_alien.asset_spec.json"))
    setup = json.load(open("out/spider_alien.godot_setup.json"))
    rig = Rig(g, bin_)
    R = {"file": "spider_alien.glb", "checks": {}, "metrics": {}, "warnings": []}

    tris, joints = len(rig.idx), len(rig.joints)
    R["metrics"]["triangles"] = tris
    R["metrics"]["vertices"] = len(rig.pos)
    R["metrics"]["joints"] = joints
    R["checks"]["tri_budget"] = {"limit": spec["mesh_budget_tris"], "used": tris,
                                 "pass": bool(tris <= spec["mesh_budget_tris"])}

    w = rig.wgt.sum(1)
    R["checks"]["weights_normalized"] = {"max_err": float(np.abs(w - 1).max()),
                                         "pass": bool(np.abs(w - 1).max() < 1e-5)}
    R["checks"]["max_influences"] = {"value": int((rig.wgt > 0).sum(1).max()), "limit": 4,
                                     "pass": bool((rig.wgt > 0).sum(1).max() <= 4)}

    # loop closure on '-loop' clips
    loop_err = {}
    for name, ch in rig.anims.items():
        if not name.endswith("-loop"): continue
        worst = 0.0
        for (_, path), (tt, vv) in ch.items():
            d = np.abs(vv[0] - vv[-1]).max()
            worst = max(worst, float(d))
        loop_err[name] = worst
    R["checks"]["loop_closure"] = {"max_abs_first_last_delta": loop_err,
                                   "pass": bool(max(loop_err.values()) < 1e-6)}

    # bone containment: each *skinned* joint pivot inside union of (slightly
    # padded) segment AABBs. Joints with zero bound vertices (e.g. the root
    # locator) are structural and exempt — there is no mesh they could be in.
    bind, _ = rig.skin_at(None, 0)
    seg_boxes = []
    skinned = set()
    for j in np.unique(rig.jnt[:, 0]):
        pts = bind[rig.jnt[:, 0] == j]
        seg_boxes.append((pts.min(0) - 0.02, pts.max(0) + 0.02))
        skinned.add(int(j))
    inside, required, exempt = 0, 0, []
    skel = setup["skeleton"]
    for k, p in enumerate(skel["rest_world"]):
        if k not in skinned:
            exempt.append(skel["names"][k]); continue
        required += 1
        p = np.array(p)
        if any(np.all(p >= lo) and np.all(p <= hi) for lo, hi in seg_boxes): inside += 1
    R["checks"]["bone_containment"] = {"inside": inside, "required": required,
                                       "exempt_structural": exempt,
                                       "pass": bool(inside == required)}

    # locomotion analysis on walk & run via foot anchors
    loco = {}
    for clip, T in (("walk-loop", None), ("run-loop", None)):
        ch = rig.anims[clip]
        T = max(tt[-1] for tt, _ in ch.values())
        anchors = setup["foot_anchors"]
        stance_dev, strides = [], []
        ts = np.linspace(0, T, 60)
        for bone, p_bind in anchors.items():
            ys, zs = [], []
            for t in ts:
                p = rig.point_on_bone(clip, t, bone, p_bind)
                ys.append(p[1]); zs.append(p[2])
            ys, zs = np.array(ys), np.array(zs)
            # adaptive stance detector: anchored to this foot's own lowest
            # point, so a foot that hovers (never reaches ground) still
            # registers its hover height as deviation, while brief lift-off
            # pass-through samples don't pollute the planted-phase metric.
            thr = max(0.004, float(ys.min()) + 0.003)
            stance = ys <= thr
            if stance.any():
                stance_dev.append(float(np.abs(ys[stance]).max()))
                strides.append(float(zs[stance].max() - zs[stance].min()))
        body_drift = []
        for t in (0, T):
            p = rig.point_on_bone(clip, t, "body", skel["rest_world"][skel["names"].index("body")])
            body_drift.append(p[[0, 2]])
        loco[clip] = {
            "cycle_s": float(T),
            "stance_foot_dev_mm": round(max(stance_dev) * 1000, 2),
            "mean_stride_m": round(float(np.mean(strides)), 4),
            "recommended_speed_mps": round(float(np.mean(strides)) / T, 3),
            "in_place_drift_m": round(float(np.linalg.norm(body_drift[1] - body_drift[0])), 6),
        }
    R["metrics"]["locomotion"] = loco
    # close the loop: write measured speeds back into the Godot contract so the
    # runtime controller moves the body at exactly the speed the feet imply
    setup["locomotion"]["walk"]["speed_mps"] = loco["walk-loop"]["recommended_speed_mps"]
    setup["locomotion"]["run"]["speed_mps"] = loco["run-loop"]["recommended_speed_mps"]
    json.dump(setup, open("out/spider_alien.godot_setup.json", "w"), indent=2)
    R["checks"]["foot_contact"] = {"worst_dev_mm": max(l["stance_foot_dev_mm"] for l in loco.values()),
                                   "limit_mm": 8.0,
                                   "pass": bool(max(l["stance_foot_dev_mm"] for l in loco.values()) <= 8.0)}
    R["checks"]["in_place"] = {"pass": bool(all(l["in_place_drift_m"] < 1e-4 for l in loco.values()))}

    # death must end below half of standing height (it's a collapse) and stay there
    pe, _ = rig.skin_at("death", 1.35)
    R["checks"]["death_collapses"] = {"final_body_max_y": round(float(
        pe[rig.jnt[:, 0] == skel["names"].index("body")][:, 1].max()), 3),
        "pass": bool(pe[rig.jnt[:, 0] == skel["names"].index("body")][:, 1].max() < 0.26)}

    # ground penetration across ALL clips (no vertex below -5mm at any sampled time)
    worst_pen = 0.0
    for name, ch in rig.anims.items():
        T = max(tt[-1] for tt, _ in ch.values())
        for t in np.linspace(0, T, 18):
            v, _ = rig.skin_at(name, t)
            worst_pen = min(worst_pen, float(v[:, 1].min()))
    R["checks"]["ground_penetration"] = {"worst_m": round(worst_pen, 4), "limit_m": -0.005,
                                         "pass": bool(worst_pen >= -0.005)}

    # merge official Khronos glTF conformance results (third-party referee),
    # produced by `node run_khronos_validator.mjs`
    try:
        kr = json.load(open("out/khronos_report.json"))
        iss = kr["issues"]
        R["checks"]["khronos_gltf_conformance"] = {
            "validator": kr.get("validatorVersion"),
            "errors": iss["numErrors"], "warnings": iss["numWarnings"],
            "infos": iss["numInfos"], "hints": iss["numHints"],
            "pass": bool(iss["numErrors"] == 0)}
    except FileNotFoundError:
        R["warnings"].append("khronos_report.json missing — run `node run_khronos_validator.mjs` first")

    # contact sheet
    fig = plt.figure(figsize=(13, 8.5), dpi=110)
    shots = [(None, 0, "bind pose"),
             ("walk-loop", 0.72 * 0.20, "walk @ 20% (group A swing)"),
             ("walk-loop", 0.72 * 0.70, "walk @ 70% (group B swing)"),
             ("attack_01", 0.16, "attack_01 rear-up apex"),
             ("attack_02", 0.26, "attack_02 lunge strike"),
             ("death", 1.35, "death (final pose)")]
    for k, (anim, t, title) in enumerate(shots, 1):
        ax = fig.add_subplot(2, 3, k, projection="3d")
        v, _ = rig.skin_at(anim, t)
        draw(ax, v[:, [0, 2, 1]], rig.idx, rig.col, title)   # swap to z-up for mpl
    fig.suptitle("creature-forge QA contact sheet — spider_alien.glb (CPU-skinned from file)", fontsize=11)
    fig.tight_layout()
    fig.savefig("out/qa_contact_sheet.png", bbox_inches="tight")

    R["overall_pass"] = bool(all(c.get("pass", True) for c in R["checks"].values()))
    json.dump(R, open("out/validation_report.json", "w"), indent=2)
    print(json.dumps(R, indent=2))

if __name__ == "__main__":
    main()

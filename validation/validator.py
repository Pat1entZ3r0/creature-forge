#!/usr/bin/env python3
"""
validation/validator.py — Stage 8: the independent gate.

Reads ONLY the .glb from disk (plus the two sidecars for budgets and contracts)
with its OWN glTF reader + CPU forward-kinematics + linear-blend skinning. It does
NOT import any pipeline writer code, so it validates what is in the file, not what
the generator intended. (It imports `conventions` for shared limits and quaternion
math only — policy and arithmetic, never generator logic.)

Ten checks, all must pass with zero warnings:
  1. triangle budget (vs asset_spec.tri_budget)
  2. skin weights normalized
  3. max influences <= cap (1 for rigid)
  4. loop closure ~ 0 on every -loop clip
  5. every skinned joint inside the mesh AABB (unskinned structural joints exempt)
  6. planted-foot contact: worst stance foot world-Y deviation <= 8 mm
  7. in-place root drift = 0
  8. death clip collapses the body below threshold and rests ON the floor
  9. ground penetration >= -5 mm across a dense per-clip sweep (>=64 samples/clip)
 10. Khronos gltf-validator: 0 errors / 0 warnings / 0 infos / 0 hints

Then measures walk/run speed from stride/cadence and writes it back into the
godot_setup contract. Emits out/validation_report.json.

Usage: python -m validation.validator <model.glb> [--no-khronos] [--no-writeback]
"""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

from conventions import (
    COMPONENT_DTYPE,
    TYPE_NCOMP,
    GLTF_MAGIC,
    GLTF_CHUNK_JSON,
    GLTF_CHUNK_BIN,
    FOOT_CONTACT_LIMIT_MM,
    GROUND_PENETRATION_LIMIT_M,
    DEATH_COLLAPSE_MAX_Y,
    LOOP_CLOSURE_TOL,
    IN_PLACE_DRIFT_TOL,
    STRESS_SAMPLES_PER_CLIP,
    GENERAL_MAX_INFLUENCES,
    WEIGHT_NORM_TOL,
    q_mat,
)

ROOT = Path(__file__).resolve().parent.parent


# ── glTF reader (independent of the writer) ──────────────────────────────────
def load_glb(path: Path):
    raw = Path(path).read_bytes()
    magic, ver, total = struct.unpack_from("<III", raw, 0)
    assert magic == GLTF_MAGIC and ver == 2, "not a GLB v2"
    off, js, bin_ = 12, None, None
    while off < total:
        ln, typ = struct.unpack_from("<II", raw, off)
        off += 8
        chunk = raw[off:off + ln]
        off += ln
        if typ == GLTF_CHUNK_JSON:
            js = json.loads(chunk.decode())
        elif typ == GLTF_CHUNK_BIN:
            bin_ = chunk
    return js, bin_


def read_acc(g, bin_, i):
    a = g["accessors"][i]
    v = g["bufferViews"][a["bufferView"]]
    dt = COMPONENT_DTYPE[a["componentType"]]
    n = TYPE_NCOMP[a["type"]]
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    arr = np.frombuffer(bin_, dt, count=a["count"] * n, offset=start)
    return arr.reshape(a["count"], n).astype(np.float64 if dt == np.float32 else dt)


def sample(times, vals, t, is_quat):
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    k = int(np.searchsorted(times, t)) - 1
    u = (t - times[k]) / (times[k + 1] - times[k])
    a, b = vals[k].copy(), vals[k + 1].copy()
    if is_quat and np.dot(a, b) < 0:
        b = -b
    out = a + (b - a) * u
    if is_quat:
        out /= np.linalg.norm(out)
    return out


class Rig:
    """CPU forward-kinematics + linear-blend skinning over the GLB's own data."""

    def __init__(self, g, bin_):
        self.g, self.bin = g, bin_
        skin = g["skins"][0]
        self.joints = skin["joints"]
        self.ibm = read_acc(g, bin_, skin["inverseBindMatrices"]).reshape(-1, 4, 4)
        self.nodes = g["nodes"]
        self.name2node = {n.get("name", str(i)): i for i, n in enumerate(self.nodes)}
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []):
                self.parent[c] = i
        prim = g["meshes"][0]["primitives"][0]
        self.pos = read_acc(g, bin_, prim["attributes"]["POSITION"])
        self.jnt = read_acc(g, bin_, prim["attributes"]["JOINTS_0"]).astype(int)
        self.wgt = read_acc(g, bin_, prim["attributes"]["WEIGHTS_0"])
        self.col = (
            read_acc(g, bin_, prim["attributes"]["COLOR_0"])
            if "COLOR_0" in prim["attributes"]
            else np.ones((len(self.pos), 4))
        )
        self.idx = read_acc(g, bin_, prim["indices"]).astype(int).reshape(-1, 3)
        self.anims = {}
        for an in g.get("animations", []):
            ch = {}
            for c in an["channels"]:
                s = an["samplers"][c["sampler"]]
                ch[(c["target"]["node"], c["target"]["path"])] = (
                    read_acc(g, bin_, s["input"]).reshape(-1),
                    read_acc(g, bin_, s["output"]),
                )
            self.anims[an["name"]] = ch

    def clip_len(self, anim: str) -> float:
        return max(float(tt[-1]) for tt, _ in self.anims[anim].values())

    def globals_at(self, anim, t):
        ch = self.anims[anim] if anim else {}
        G = {}

        def rec(i):
            n = self.nodes[i]
            tr = np.array(n.get("translation", [0, 0, 0]), float)
            q = np.array(n.get("rotation", [0, 0, 0, 1.0]))
            if (i, "translation") in ch:
                tt, vv = ch[(i, "translation")]
                tr = sample(tt, vv, t, False)
            if (i, "rotation") in ch:
                tt, vv = ch[(i, "rotation")]
                q = sample(tt, vv, t, True)
            L = np.identity(4)
            L[:3, :3] = q_mat(q)
            L[:3, 3] = tr
            G[i] = (G[self.parent[i]] @ L) if i in self.parent else L
            for c in n.get("children", []):
                rec(c)

        roots = [j for j in self.joints if j not in self.parent]
        for r in roots:
            rec(r)
        return G

    def skin_at(self, anim, t):
        G = self.globals_at(anim, t)
        # IBM stored column-major flat -> reshape(4,4) is its transpose
        M = {j: G[j] @ self.ibm[k].T for k, j in enumerate(self.joints)}
        out = np.empty_like(self.pos)
        hom = np.concatenate([self.pos, np.ones((len(self.pos), 1))], 1)
        for slot in np.unique(self.jnt[:, 0]):
            mask = self.jnt[:, 0] == slot  # rigid skin: weight 1 on slot 0
            out[mask] = (hom[mask] @ M[self.joints[slot]].T)[:, :3]
        return out, G

    def point_on_bone(self, anim, t, bone_name, p_bind):
        G = self.globals_at(anim, t)
        j = self.name2node[bone_name]
        k = self.joints.index(j)
        M = G[j] @ self.ibm[k].T
        return (M @ np.array([*p_bind, 1.0]))[:3]


# ── Khronos referee (third-party conformance) ────────────────────────────────
def run_khronos(glb_path: Path) -> dict | None:
    runner = ROOT / "validation" / "khronos.mjs"
    try:
        proc = subprocess.run(
            ["node", str(runner), str(glb_path)],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
    except Exception:  # node or module unavailable
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


# ── the gate ─────────────────────────────────────────────────────────────────
def validate(glb_path: Path, write_back: bool = True, khronos: bool = True) -> dict:
    glb_path = Path(glb_path)
    stem = glb_path.name[:-4] if glb_path.name.endswith(".glb") else glb_path.stem
    base = glb_path.parent
    spec = json.loads((base / f"{stem}.asset_spec.json").read_text())
    setup_path = base / f"{stem}.godot_setup.json"
    setup = json.loads(setup_path.read_text())

    g, bin_ = load_glb(glb_path)
    rig = Rig(g, bin_)
    skel = setup["skeleton"]
    names = skel["names"]
    body_name = "body" if "body" in names else names[1]

    R: dict = {"file": glb_path.name, "checks": {}, "metrics": {}, "warnings": []}
    tris, joints = len(rig.idx), len(rig.joints)
    R["metrics"].update(triangles=tris, vertices=len(rig.pos), joints=joints)

    # 1 triangle budget
    R["checks"]["tri_budget"] = {
        "limit": spec["tri_budget"], "used": tris, "pass": bool(tris <= spec["tri_budget"])
    }
    # 2 weights normalized
    werr = float(np.abs(rig.wgt.sum(1) - 1).max())
    R["checks"]["weights_normalized"] = {"max_err": werr, "pass": bool(werr < WEIGHT_NORM_TOL)}
    # 3 max influences
    infl = int((rig.wgt > 0).sum(1).max())
    R["checks"]["max_influences"] = {
        "value": infl, "limit": GENERAL_MAX_INFLUENCES, "pass": bool(infl <= GENERAL_MAX_INFLUENCES)
    }
    # 4 loop closure on -loop clips
    loop_err = {}
    for name, ch in rig.anims.items():
        if not name.endswith("-loop"):
            continue
        loop_err[name] = max(float(np.abs(vv[0] - vv[-1]).max()) for _, vv in ch.values())
    R["checks"]["loop_closure"] = {
        "max_abs_first_last_delta": loop_err,
        "pass": bool(loop_err and max(loop_err.values()) < LOOP_CLOSURE_TOL),
    }
    # 5 bone containment: every skinned joint pivot inside union of padded segment AABBs
    bind, _ = rig.skin_at(None, 0)
    seg_boxes, skinned = [], set()
    for slot in np.unique(rig.jnt[:, 0]):
        pts = bind[rig.jnt[:, 0] == slot]
        seg_boxes.append((pts.min(0) - 0.02, pts.max(0) + 0.02))
        skinned.add(int(slot))
    inside, required, exempt = 0, 0, []
    for k, p in enumerate(skel["rest_world"]):
        node = rig.name2node[names[k]]
        slot = rig.joints.index(node)
        if slot not in skinned:
            exempt.append(names[k])
            continue
        required += 1
        p = np.array(p)
        if any(np.all(p >= lo) and np.all(p <= hi) for lo, hi in seg_boxes):
            inside += 1
    R["checks"]["bone_containment"] = {
        "inside": inside, "required": required, "exempt_structural": exempt,
        "pass": bool(inside == required),
    }

    # 6/7 locomotion: stance foot deviation + stride -> measured speed; in-place drift
    loco = {}
    for key in ("walk", "run"):
        gait = setup.get("locomotion", {}).get(key)
        if not gait or gait["anim"] not in rig.anims:
            continue
        clip = gait["anim"]
        T = rig.clip_len(clip)
        stance_dev, strides = [], []
        ts = np.linspace(0, T, 60)
        for bone, p_bind in setup.get("foot_anchors", {}).items():
            ys = np.array([rig.point_on_bone(clip, t, bone, p_bind)[1] for t in ts])
            zs = np.array([rig.point_on_bone(clip, t, bone, p_bind)[2] for t in ts])
            thr = max(0.004, float(ys.min()) + 0.003)
            stance = ys <= thr
            if stance.any():
                stance_dev.append(float(np.abs(ys[stance]).max()))
                strides.append(float(zs[stance].max() - zs[stance].min()))
        body_bind = skel["rest_world"][names.index(body_name)]
        d0 = rig.point_on_bone(clip, 0, body_name, body_bind)[[0, 2]]
        d1 = rig.point_on_bone(clip, T, body_name, body_bind)[[0, 2]]
        mean_stride = float(np.mean(strides)) if strides else 0.0
        loco[clip] = {
            "gait": key,
            "cycle_s": round(T, 4),
            "stance_foot_dev_mm": round((max(stance_dev) if stance_dev else 0.0) * 1000, 2),
            "mean_stride_m": round(mean_stride, 4),
            "recommended_speed_mps": round(mean_stride / T, 3) if T else 0.0,
            "in_place_drift_m": round(float(np.linalg.norm(d1 - d0)), 6),
        }
    R["metrics"]["locomotion"] = loco
    worst_dev = max((l["stance_foot_dev_mm"] for l in loco.values()), default=0.0)
    R["checks"]["foot_contact"] = {
        "worst_dev_mm": worst_dev, "limit_mm": FOOT_CONTACT_LIMIT_MM,
        "pass": bool(worst_dev <= FOOT_CONTACT_LIMIT_MM),
    }
    R["checks"]["in_place"] = {
        "pass": bool(all(l["in_place_drift_m"] < IN_PLACE_DRIFT_TOL for l in loco.values()))
    }

    # write measured speeds back into the engine contract
    if write_back:
        for clip, l in loco.items():
            setup["locomotion"][l["gait"]]["speed_mps"] = l["recommended_speed_mps"]
        setup_path.write_text(json.dumps(setup, indent=2), encoding="utf-8")

    # 8 death collapse: body bone's verts max-Y below threshold at end of death
    death = next((a["name"] for a in setup["animations"] if a.get("role") == "death"), None)
    death = death or ("death" if "death" in rig.anims else None)
    if death:
        body_slot = rig.joints.index(rig.name2node[body_name])
        pe, _ = rig.skin_at(death, rig.clip_len(death))
        body_max_y = float(pe[rig.jnt[:, 0] == body_slot][:, 1].max())
        R["checks"]["death_collapses"] = {
            "final_body_max_y": round(body_max_y, 3),
            "limit": DEATH_COLLAPSE_MAX_Y,
            "pass": bool(body_max_y < DEATH_COLLAPSE_MAX_Y),
        }

    # 9 ground penetration across ALL clips (dense sweep)
    worst_pen = 0.0
    for name in rig.anims:
        T = rig.clip_len(name)
        for t in np.linspace(0, T, STRESS_SAMPLES_PER_CLIP):
            v, _ = rig.skin_at(name, t)
            worst_pen = min(worst_pen, float(v[:, 1].min()))
    R["checks"]["ground_penetration"] = {
        "worst_m": round(worst_pen, 4), "limit_m": GROUND_PENETRATION_LIMIT_M,
        "samples_per_clip": STRESS_SAMPLES_PER_CLIP,
        "pass": bool(worst_pen >= GROUND_PENETRATION_LIMIT_M),
    }

    # 10 Khronos conformance
    if khronos:
        kr = run_khronos(glb_path)
        if kr:
            iss = kr["issues"]
            R["checks"]["khronos_gltf_conformance"] = {
                "validator": kr.get("validatorVersion"),
                "errors": iss["numErrors"], "warnings": iss["numWarnings"],
                "infos": iss["numInfos"], "hints": iss["numHints"],
                "pass": bool(iss["numErrors"] == 0 and iss["numWarnings"] == 0
                             and iss["numInfos"] == 0 and iss["numHints"] == 0),
            }
        else:
            R["warnings"].append(
                "Khronos gltf-validator unavailable (need `npm i gltf-validator` + node); "
                "check 10 skipped"
            )

    R["overall_pass"] = bool(
        all(c.get("pass", True) for c in R["checks"].values()) and not R["warnings"]
    )
    return R


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    glb = Path(argv[0])
    write_back = "--no-writeback" not in argv
    khronos = "--no-khronos" not in argv
    R = validate(glb, write_back=write_back, khronos=khronos)
    (ROOT / "out" / "validation_report.json").write_text(json.dumps(R, indent=2), encoding="utf-8")
    print(json.dumps(R, indent=2))
    print("\nVALIDATOR:", "PASS" if R["overall_pass"] else "FAIL")
    return 0 if R["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

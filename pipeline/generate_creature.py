#!/usr/bin/env python3
"""
generate_creature.py — Stage 5/6/7 reference implementation of a Godot-first
AI asset pipeline ("creature forge").

This module realizes the ARACHNID rig archetype end to end WITHOUT any ML model:
  spec -> skeleton (archetype template) -> mesh segments (procedural stand-in
  for the generative-mesh stage) -> rigid skinning -> procedural animation set
  (idle / walk / run / attack_01 / attack_02 / hit / death) -> spec-compliant
  GLB -> Godot sidecar metadata (godot_setup.json) -> asset_spec.json echo.

Design decisions that matter:
  * All bind-pose bone rotations are IDENTITY; bones are placed by translation
    only. Inverse bind matrices are therefore pure translations, animation
    rotations operate in world-aligned local axes, and every downstream tool
    (validator, Godot, retarget layer) can reason about the rig trivially.
  * Every animation clip writes channels for the FULL controlled bone set,
    even when constant. This keeps AnimationTree cross-fades deterministic
    (no stale-pose bleed between states).
  * In-place locomotion (no root motion). The Godot controller moves the
    CharacterBody3D and the measured stride (see validate_asset.py) tells it
    the speed at which feet do not slide.
  * Loop clips ("-loop" suffix, Godot import convention) have first == last
    keys exactly.

Units: meters. Up: +Y. Forward: -Z (glTF / Godot convention).
Quaternions: x, y, z, w (glTF order).
"""

import json
import struct
import numpy as np

# ----------------------------------------------------------------------------
# small math kit
# ----------------------------------------------------------------------------

def q_axis(axis, deg):
    """Quaternion (xyzw) from axis + angle in degrees."""
    a = np.asarray(axis, dtype=np.float64)
    a = a / np.linalg.norm(a)
    h = np.radians(deg) * 0.5
    s = np.sin(h)
    return np.array([a[0] * s, a[1] * s, a[2] * s, np.cos(h)], dtype=np.float64)

Q_ID = np.array([0.0, 0.0, 0.0, 1.0])

def q_mul(qa, qb):
    """Hamilton product, xyzw storage. R(q_mul(a,b)) = R(a) @ R(b): b applies first."""
    ax, ay, az, aw = qa
    bx, by, bz, bw = qb
    return np.array([
        aw * bx + bw * ax + (ay * bz - az * by),
        aw * by + bw * ay + (az * bx - ax * bz),
        aw * bz + bw * az + (ax * by - ay * bx),
        aw * bw - (ax * bx + ay * by + az * bz),
    ])

def leg_rot(side, lift_deg, swing_deg, splay_deg=0.0):
    """
    Compose a leg-bone rotation from intuitive parameters.
      side: +1 = left leg (points +X), -1 = right leg (points -X)
      lift: positive raises the foot   (about Z, sign flips per side)
      swing: positive moves foot forward, i.e. toward -Z (about Y, sign flips per side)
      splay: positive spreads outward in the XZ plane (about Y, same per side... folded into swing axis)
    Extrinsic order: swing first, then lift (lift axis stays world-Z).
    """
    qs = q_axis([0, 1, 0], (swing_deg + splay_deg) * side)
    ql = q_axis([0, 0, 1], lift_deg * side)
    return q_mul(ql, qs)

def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)

def bell(t):
    return np.sin(np.pi * np.clip(t, 0.0, 1.0))

# ----------------------------------------------------------------------------
# 1. compiled asset spec (Stage 1 output — here authored to mirror the source
#    document's own example prompt: "small venomous spider alien, low-poly
#    PS1 horror style, fast skittering movement, attack animations, death")
# ----------------------------------------------------------------------------

ASSET_SPEC = {
    "spec_version": "0.1",
    "prompt": "small venomous spider alien, low-poly PS1 horror style, fast skittering movement, multiple attacks, death animation",
    "style": "low_poly_ps1_horror",
    "target_engine": "godot4",
    "units": "meters",
    "axes": {"up": "+Y", "forward": "-Z"},
    "scale_hint": {"body_length_m": 0.62, "stance_height_m": 0.21},
    "mesh_budget_tris": 1800,
    "texture": {"mode": "vertex_color", "atlas_px": None,
                "note": "v0 ships flat-shaded vertex colors (PS1-authentic); 256px atlas slot reserved for the bake stage"},
    "palette": "muted_green_purple",
    "rig_archetype": "arachnid",
    "limbs": 8,
    "animations": ["idle", "walk", "run", "attack_01", "attack_02", "hit", "death"],
    "export": "glb",
    "seed": 1337,
}

# ----------------------------------------------------------------------------
# 2. ARACHNID archetype: skeleton template
#    (name, parent_name, world_position). Identity bind rotations everywhere.
# ----------------------------------------------------------------------------

HIP_X, HIP_Y = 0.125, 0.205
KNEE_X, KNEE_Y = 0.335, 0.355
FOOT_X = 0.46
LEG_Z = [-0.150, -0.055, 0.040, 0.135]          # front -> back hip attach z
KNEE_SPLAY = [-0.060, -0.020, 0.020, 0.060]      # fronts splay fwd, rears back
FOOT_SPLAY_MULT = 2.1

def build_skeleton():
    bones = [
        ("root",    None,   (0.0, 0.0, 0.0)),
        ("body",    "root", (0.0, 0.21, -0.02)),
        ("abdomen", "body", (0.0, 0.25, 0.20)),
        ("head",    "body", (0.0, 0.20, -0.22)),
        ("fang_l",  "head", ( 0.035, 0.155, -0.285)),
        ("fang_r",  "head", (-0.035, 0.155, -0.285)),
    ]
    for i, z in enumerate(LEG_Z, start=1):
        for side, tag in ((+1, "l"), (-1, "r")):
            hip = (side * HIP_X, HIP_Y, z)
            knee = (side * KNEE_X, KNEE_Y, z + KNEE_SPLAY[i - 1])
            bones.append((f"hip_{tag}{i}", "body", hip))
            bones.append((f"tib_{tag}{i}", f"hip_{tag}{i}", knee))
    names = [b[0] for b in bones]
    idx = {n: k for k, n in enumerate(names)}
    parents = [(-1 if b[1] is None else idx[b[1]]) for b in bones]
    world = np.array([b[2] for b in bones], dtype=np.float64)
    return names, idx, parents, world

NAMES, IDX, PARENTS, WORLD = build_skeleton()

def foot_pos(side, i):
    z = LEG_Z[i - 1] + KNEE_SPLAY[i - 1] * FOOT_SPLAY_MULT
    return np.array([side * FOOT_X, 0.0, z])

def knee_pos(side, i):
    return WORLD[IDX[f"tib_{'l' if side > 0 else 'r'}{i}"]]

def hip_pos(side, i):
    return WORLD[IDX[f"hip_{'l' if side > 0 else 'r'}{i}"]]

# ----------------------------------------------------------------------------
# 3. procedural low-poly mesh (stand-in for the generative-mesh stage)
#    Every segment is a flat-shaded box rigidly bound to exactly one bone.
# ----------------------------------------------------------------------------

PAL = {
    "body":    (0.215, 0.165, 0.300),
    "abdomen": (0.265, 0.205, 0.360),
    "stripe":  (0.190, 0.330, 0.215),
    "head":    (0.235, 0.180, 0.320),
    "leg_a":   (0.160, 0.130, 0.225),
    "leg_b":   (0.135, 0.108, 0.195),
    "fang":    (0.840, 0.815, 0.700),
    "eye":     (0.330, 0.950, 0.420),
}

class MeshBank:
    def __init__(self):
        self.pos, self.nrm, self.col, self.jnt, self.idxs = [], [], [], [], []
        self.vcount = 0
        self.foot_anchor = {}   # bone name -> world point rigid to that bone (QA probes)

    def _emit_quad(self, a, b, c, d, color, bone):
        n = np.cross(np.asarray(c) - np.asarray(a), np.asarray(b) - np.asarray(a))
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-9 else np.array([0, 1, 0.0])
        base = self.vcount
        for p in (a, b, c, d):
            self.pos.append(p); self.nrm.append(n)
            self.col.append((*color, 1.0)); self.jnt.append(bone)
        self.idxs += [base, base + 2, base + 1, base, base + 3, base + 2]
        self.vcount += 4

    def oriented_box(self, p0, p1, w, d, color, bone, taper=1.0, up_hint=(0, 1, 0)):
        p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
        ax = p1 - p0; ax = ax / np.linalg.norm(ax)
        up = np.asarray(up_hint, float)
        if abs(np.dot(ax, up)) > 0.92:
            up = np.array([1.0, 0, 0])
        s = np.cross(up, ax); s /= np.linalg.norm(s)
        u = np.cross(ax, s)
        hw0, hd0 = w / 2, d / 2
        hw1, hd1 = hw0 * taper, hd0 * taper
        c = [p0 + s*hw0 + u*hd0, p0 - s*hw0 + u*hd0, p0 - s*hw0 - u*hd0, p0 + s*hw0 - u*hd0,
             p1 + s*hw1 + u*hd1, p1 - s*hw1 + u*hd1, p1 - s*hw1 - u*hd1, p1 + s*hw1 - u*hd1]
        E = self._emit_quad
        E(c[3], c[2], c[1], c[0], color, bone)            # cap p0
        E(c[4], c[5], c[6], c[7], color, bone)            # cap p1
        E(c[0], c[1], c[5], c[4], color, bone)
        E(c[1], c[2], c[6], c[5], color, bone)
        E(c[2], c[3], c[7], c[6], color, bone)
        E(c[3], c[0], c[4], c[7], color, bone)

    def aabox(self, center, size, color, bone):
        c = np.asarray(center, float); h = np.asarray(size, float) / 2
        self.oriented_box(c - [0, 0, h[2]], c + [0, 0, h[2]], size[0], size[1],
                          color, bone, up_hint=(0, 1, 0))

def build_mesh():
    mb = MeshBank()
    body_i, abd_i, head_i = IDX["body"], IDX["abdomen"], IDX["head"]
    # cephalothorax + abdomen + dorsal stripe + head
    mb.aabox((0, 0.215, -0.045), (0.225, 0.150, 0.300), PAL["body"], body_i)
    mb.aabox((0, 0.255, 0.215), (0.300, 0.215, 0.290), PAL["abdomen"], abd_i)
    mb.aabox((0, 0.368, 0.215), (0.105, 0.018, 0.230), PAL["stripe"], abd_i)
    mb.aabox((0, 0.205, -0.245), (0.150, 0.115, 0.130), PAL["head"], head_i)
    # eyes (two emerald chips) + fangs (rigid to their own bones)
    for sx in (+1, -1):
        mb.aabox((sx * 0.037, 0.236, -0.308), (0.030, 0.026, 0.012), PAL["eye"], head_i)
        bone = IDX[f"fang_{'l' if sx > 0 else 'r'}"]
        f0 = np.array([sx * 0.035, 0.158, -0.285])
        f1 = np.array([sx * 0.028, 0.085, -0.335])
        mb.oriented_box(f0, f1, 0.030, 0.030, PAL["fang"], bone, taper=0.25)
    # legs: femur (hip box -> knee) and tibia (knee -> foot), tapered
    for i in range(1, 5):
        for side, tag in ((+1, "l"), (-1, "r")):
            hp, kp, fp = hip_pos(side, i), knee_pos(side, i), foot_pos(side, i)
            col = PAL["leg_a"] if (i % 2 == 1) else PAL["leg_b"]
            mb.oriented_box(hp, kp, 0.052, 0.052, col, IDX[f"hip_{tag}{i}"], taper=0.78)
            tib_bone = IDX[f"tib_{tag}{i}"]
            mb.oriented_box(kp, fp, 0.040, 0.040, col, tib_bone, taper=0.22)
            mb.foot_anchor[f"tib_{tag}{i}"] = fp.tolist()
    return mb

# Build the mesh once at module level: the animation stage needs the actual
# tibia geometry to solve foot planting against the real lowest vertices.
MB = build_mesh()

# Tibia verts in tib-local space (bind rotations are identity, so local =
# world - bone_bind_world). Used by the planted-foot solver.
TIB_VERTS = {}
for _i in range(1, 5):
    for _side, _tag in ((+1, "l"), (-1, "r")):
        _name = f"{_tag}{_i}"
        _bone = IDX[f"tib_{_name}"]
        _vs = np.array([p for p, b in zip(MB.pos, MB.jnt) if b == _bone])
        TIB_VERTS[_name] = _vs - knee_pos(_side, _i)

# ----------------------------------------------------------------------------
# 3b. planted-foot solver
#     Procedural gait + body motion is authored in joint space, but ground
#     contact is a *world-space* constraint. For every key where a leg should
#     be planted, we bisect the hip lift angle so that the leg's lowest mesh
#     vertex sits at GROUND_TARGET (a 2.5 mm "dig", comfortably inside the
#     validator's -5 mm penetration limit). This is the per-archetype IK the
#     critique argues every generated-creature pipeline needs.
# ----------------------------------------------------------------------------

GROUND_TARGET = -0.0025

def q_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w),     2 * (x * z + y * w)],
        [2 * (x * y + z * w),     1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w),     2 * (y * z + x * w),     1 - 2 * (x * x + y * y)],
    ])

def leg_min_y(tag, body_q, body_t, hip_q, tib_q):
    """Lowest world-y over the tibia segment's actual mesh verts for a pose."""
    side, i = (+1 if tag[0] == "l" else -1), int(tag[1])
    hipw, kneew = hip_pos(side, i), knee_pos(side, i)
    t_hip = hipw - WORLD[IDX["body"]]
    t_tib = kneew - hipw
    Rb, Rh, Rt = q_mat(body_q), q_mat(hip_q), q_mat(tib_q)
    pts = np.asarray(body_t) + (Rb @ (t_hip[:, None] + Rh @ (
        t_tib[:, None] + Rt @ TIB_VERTS[tag].T))).T
    return float(pts[:, 1].min())

def planted_lift(tag, swing, body_q=Q_ID, body_t=None, tib_q=Q_ID,
                 target=GROUND_TARGET):
    """Bisect the hip lift angle so the leg's lowest vertex rests at target-y."""
    if body_t is None:
        body_t = BODY_BIND_T
    side = +1 if tag[0] == "l" else -1
    f = lambda L: leg_min_y(tag, body_q, body_t,
                            leg_rot(side, L, swing), tib_q) - target
    lo, hi = -40.0, 82.0
    flo, fhi = f(lo), f(hi)
    if flo > 0 or fhi < 0:                       # target unreachable: clamp
        return lo if abs(flo) < abs(fhi) else hi
    for _ in range(44):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

# Generic whole-pose evaluator (used by the death ground clamp).
LOCAL_T = WORLD - np.array([WORLD[p] if p >= 0 else (0, 0, 0) for p in PARENTS])
ALL_POS = np.array(MB.pos)
ALL_JNT = np.array(MB.jnt)
VERT_LOCAL = ALL_POS - WORLD[ALL_JNT]            # rigid bind: local = world - pivot

def pose_min_y(pose_rot, pose_trs):
    """Min world-y of every mesh vertex for a static pose.
    pose_rot: {bone: quat}, pose_trs: {bone: local translation override}."""
    Rg = [None] * len(NAMES); Tg = [None] * len(NAMES)
    for k, name in enumerate(NAMES):
        R = q_mat(pose_rot.get(name, Q_ID))
        t = np.asarray(pose_trs.get(name, LOCAL_T[k]), float)
        p = PARENTS[k]
        if p < 0:
            Rg[k], Tg[k] = R, t
        else:
            Rg[k] = Rg[p] @ R
            Tg[k] = Tg[p] + Rg[p] @ t
    ys = np.empty(len(ALL_POS))
    for k in range(len(NAMES)):
        m = ALL_JNT == k
        if m.any():
            ys[m] = (VERT_LOCAL[m] @ Rg[k].T + Tg[k])[:, 1]
    return float(ys.min())

# ----------------------------------------------------------------------------
# 4. animation clips
#    Each clip = dict: name -> { "len": seconds, "loop": bool,
#                                "rot": {bone_name: [(t, quat)]},
#                                "trs": {bone_name: [(t, vec3_local)]} }
#    Bones absent from a clip get constant identity / bind keys injected later.
# ----------------------------------------------------------------------------

LEG_TAGS = [f"{s}{i}" for i in range(1, 5) for s in ("l", "r")]
GROUP_A = {"l1", "r2", "l3", "r4"}          # alternating tetrapod
BODY_BIND_T = (WORLD[IDX["body"]] - WORLD[IDX["root"]]).tolist()

def leg_cycle_pose(tag, phase, lift_max, swing_fwd, swing_back, tib_fold):
    """One leg's raw gait parameters at a normalized phase in [0,1).
    Returns (raw_lift, swing_deg, tib_quat). raw_lift is the swing-arc height
    ON TOP of the planted baseline solved per key by the caller."""
    side = +1 if tag[0] == "l" else -1
    p = phase % 1.0
    SW = 0.42                                  # swing fraction of the cycle
    if p < SW:                                 # swing: lift + reach forward
        s = p / SW
        raw_lift = lift_max * bell(s)
        swing = swing_back + (swing_fwd - swing_back) * smoothstep(s)
        tib = tib_fold * bell(s)
    else:                                      # stance: planted, sweep back
        s = (p - SW) / (1 - SW)
        raw_lift = 0.0
        swing = swing_fwd + (swing_back - swing_fwd) * s
        tib = 0.0
    return raw_lift, swing, leg_rot(side, tib * 0.55, -tib * 0.35)

def make_locomotion(name, T, lift_max, swing_fwd, swing_back, tib_fold,
                    bob_amp, bob_hz, n_keys=17):
    rot, trs = {f"hip_{t}": [] for t in LEG_TAGS}, {}
    rot.update({f"tib_{t}": [] for t in LEG_TAGS})
    trs["body"] = []
    for k in range(n_keys):
        u = k / (n_keys - 1)                   # 0..1 inclusive (loop closure)
        t = u * T
        bob = bob_amp * np.sin(2 * np.pi * bob_hz * u)
        body_t = [BODY_BIND_T[0], BODY_BIND_T[1] + bob, BODY_BIND_T[2]]
        trs["body"].append((t, body_t))
        for tag in LEG_TAGS:
            side = +1 if tag[0] == "l" else -1
            ph = u if tag in GROUP_A else u + 0.5
            raw_lift, swing, tq = leg_cycle_pose(tag, ph, lift_max,
                                                 swing_fwd, swing_back, tib_fold)
            base = planted_lift(tag, swing, Q_ID, body_t, tq)
            rot[f"hip_{tag}"].append((t, leg_rot(side, base + raw_lift, swing)))
            rot[f"tib_{tag}"].append((t, tq))
    # exact loop closure
    for ch in (rot, trs):
        for k in ch: ch[k][-1] = (T, ch[k][0][1])
    return {"len": T, "loop": True, "rot": rot, "trs": trs}

def make_idle():
    T, n = 1.8, 13
    rot = {"abdomen": [], "body": [], "fang_l": [], "fang_r": []}
    rot.update({f"hip_{t}": [] for t in LEG_TAGS})
    trs = {"body": []}
    for k in range(n):
        u = k / (n - 1); t = u * T
        breathe = np.sin(2 * np.pi * u)
        body_t = [BODY_BIND_T[0], BODY_BIND_T[1] + 0.006 * breathe, BODY_BIND_T[2]]
        body_q = q_axis([1, 0, 0], 0.8 * breathe)
        trs["body"].append((t, body_t))
        rot["body"].append((t, body_q))
        rot["abdomen"].append((t, q_axis([1, 0, 0], 2.8 * np.sin(2 * np.pi * u + 0.9))))
        fl = 4.0 * max(0.0, np.sin(2 * np.pi * u * 2)) * (1 if 0.45 < u < 0.8 else 0.15)
        rot["fang_l"].append((t, q_axis([1, 0, 0], -fl)))
        rot["fang_r"].append((t, q_axis([1, 0, 0], -fl)))
        twitch = {"l2": 3.0 * bell((u * 3) % 1 if u < 0.34 else 0),
                  "r3": 3.0 * bell(((u - 0.55) * 3) % 1 if 0.55 < u < 0.89 else 0)}
        for tag in LEG_TAGS:
            side = +1 if tag[0] == "l" else -1
            base = planted_lift(tag, 0.0, body_q, body_t)
            rot[f"hip_{tag}"].append((t, leg_rot(side, base + twitch.get(tag, 0.0), 0.0)))
    for ch in (rot, trs):
        for k2 in ch: ch[k2][-1] = (T, ch[k2][0][1])
    return {"len": T, "loop": True, "rot": rot, "trs": trs}

def _front_pair_tags(npairs=2):
    return [f"{s}{i}" for i in range(1, npairs + 1) for s in ("l", "r")]

def make_attack_rearup():
    """attack_01: rear up on back legs, slam front pairs down. Hit window in metadata.
    Back legs are *solved* planted against the pitching body at every key;
    front legs are authored at the airborne apex and solved to plant on the
    slam / hold / recovery keys. Keys are densified with midpoints so the
    planted constraint also bounds the interpolated in-betweens."""
    T = 0.62
    A_KEY = [0.0, 0.16, 0.30, 0.40, 0.50, 0.62]          # windup apex strike hold recover
    a_rx = [0, 26, -9, -7, -2, 0]
    a_dy = [0, 0.055, -0.012, -0.010, 0.0, 0]
    a_op = [10, 28, 4, 10, 10, 10]                       # fang flare
    a_swing_f = [0, 14, 26, 24, 8, 0]                    # front legs
    a_fold_f = [0, -18, 30, 26, 8, 0]
    a_lift_f = [None, 52, None, None, None, None]        # None => solve planted
    a_swing_b = [0, -10, -4, 0, 0, 0]                    # back-leg grip
    KEY = []
    for j in range(len(A_KEY) - 1):
        KEY += [A_KEY[j], 0.5 * (A_KEY[j] + A_KEY[j + 1])]
    KEY.append(A_KEY[-1])
    L = lambda arr: np.interp(KEY, A_KEY, arr)
    rx, dy, op = L(a_rx), L(a_dy), L(a_op)
    swing_f, fold_f, swing_b = L(a_swing_f), L(a_fold_f), L(a_swing_b)

    rot = {f"hip_{t}": [] for t in LEG_TAGS}
    rot.update({f"tib_{t}": [] for t in LEG_TAGS})
    rot.update({"body": [], "fang_l": [], "fang_r": []})
    trs = {"body": []}
    body_Q, body_T = [], []
    for j, t in enumerate(KEY):
        bq = q_axis([1, 0, 0], rx[j])
        bt = [BODY_BIND_T[0], BODY_BIND_T[1] + dy[j], BODY_BIND_T[2]]
        body_Q.append(bq); body_T.append(bt)
        rot["body"].append((t, bq))
        trs["body"].append((t, bt))
        rot["fang_l"].append((t, q_axis([1, 0, 0], -op[j])))
        rot["fang_r"].append((t, q_axis([1, 0, 0], -op[j])))
    front = set(_front_pair_tags(2))
    for tag in LEG_TAGS:
        side = +1 if tag[0] == "l" else -1
        if tag in front:
            # resolve authored keys first (solve where None), then fill midpoints
            resolved = []
            for j, ak in enumerate(A_KEY):
                tq = leg_rot(side, a_fold_f[j], -a_fold_f[j] * 0.4)
                if a_lift_f[j] is None:
                    bq = q_axis([1, 0, 0], a_rx[j])
                    bt = [BODY_BIND_T[0], BODY_BIND_T[1] + a_dy[j], BODY_BIND_T[2]]
                    resolved.append(planted_lift(tag, a_swing_f[j], bq, bt, tq))
                else:
                    resolved.append(float(a_lift_f[j]))
            for j, t in enumerate(KEY):
                tq = leg_rot(side, fold_f[j], -fold_f[j] * 0.4)
                if t in A_KEY:
                    lift = resolved[A_KEY.index(t)]
                else:                                    # midpoint of segment s
                    s = next(i for i in range(len(A_KEY) - 1)
                             if A_KEY[i] < t < A_KEY[i + 1])
                    planted_seg = a_lift_f[s] is None and a_lift_f[s + 1] is None
                    if planted_seg:
                        lift = planted_lift(tag, swing_f[j], body_Q[j], body_T[j], tq)
                    else:                                # airborne arc: lerp resolved
                        lift = 0.5 * (resolved[s] + resolved[s + 1])
                rot[f"hip_{tag}"].append((t, leg_rot(side, lift, swing_f[j])))
                rot[f"tib_{tag}"].append((t, tq))
        else:                                            # back legs: always planted
            for j, t in enumerate(KEY):
                lift = planted_lift(tag, swing_b[j], body_Q[j], body_T[j])
                rot[f"hip_{tag}"].append((t, leg_rot(side, lift, swing_b[j])))
                rot[f"tib_{tag}"].append((t, Q_ID.copy()))
    return {"len": T, "loop": False, "rot": rot, "trs": trs}

def make_attack_lunge():
    """attack_02: forward lunge bite — body thrusts to -Z, fangs snap.
    Legs are keyed at the body's own keys with solved planted lift, so the
    feet visibly anchor and drag-grip while the body coils and thrusts."""
    T = 0.52
    rot = {"body": [], "head": [], "fang_l": [], "fang_r": []}
    trs = {"body": []}
    A_KEY = [0.0, 0.14, 0.26, 0.36, 0.52]
    a_dz = [0, 0.045, -0.085, -0.070, 0]                # coil back, thrust forward
    a_rx = [0, 8, -12, -10, 0]
    a_fang = [8, 34, 2, 4, 8]
    a_grip = [0, 3.2, 6, 3.7, 0]                        # grip swing
    KEY = []
    for j in range(len(A_KEY) - 1):
        KEY += [A_KEY[j], 0.5 * (A_KEY[j] + A_KEY[j + 1])]
    KEY.append(A_KEY[-1])
    L = lambda arr: np.interp(KEY, A_KEY, arr)
    dz, rx, fang, grip = L(a_dz), L(a_rx), L(a_fang), L(a_grip)
    body_T, body_Q = [], []
    for j, t in enumerate(KEY):
        bt = [BODY_BIND_T[0], BODY_BIND_T[1], BODY_BIND_T[2] + dz[j]]
        bq = q_axis([1, 0, 0], rx[j])
        body_T.append(bt); body_Q.append(bq)
        trs["body"].append((t, bt))
        rot["body"].append((t, bq))
        rot["head"].append((t, q_axis([1, 0, 0], rx[j] * 0.7)))
        rot["fang_l"].append((t, q_axis([1, 0, 0], -fang[j])))
        rot["fang_r"].append((t, q_axis([1, 0, 0], -fang[j])))
    for tag in LEG_TAGS:
        side = +1 if tag[0] == "l" else -1
        rot[f"hip_{tag}"] = []
        for j, t in enumerate(KEY):
            lift = planted_lift(tag, grip[j], body_Q[j], body_T[j])
            rot[f"hip_{tag}"].append((t, leg_rot(side, lift, grip[j])))
    return {"len": T, "loop": False, "rot": rot, "trs": trs}

def make_hit():
    T = 0.34
    rot, trs = {"body": []}, {"body": []}
    A_KEY = [0.0, 0.08, 0.20, 0.34]
    a_z = [0, 0.05, 0.018, 0]
    a_x = [0, -9, -3, 0]
    a_flinch = [0, -5.6, -4.1, 0]                       # leg swing
    KEY = []
    for j in range(len(A_KEY) - 1):
        KEY += [A_KEY[j], 0.5 * (A_KEY[j] + A_KEY[j + 1])]
    KEY.append(A_KEY[-1])
    L = lambda arr: np.interp(KEY, A_KEY, arr)
    z, x, flinch = L(a_z), L(a_x), L(a_flinch)
    body_T, body_Q = [], []
    for j, t in enumerate(KEY):
        bt = [BODY_BIND_T[0], BODY_BIND_T[1], BODY_BIND_T[2] + z[j]]
        bq = q_axis([1, 0, 0], x[j])
        body_T.append(bt); body_Q.append(bq)
        trs["body"].append((t, bt))
        rot["body"].append((t, bq))
    for tag in LEG_TAGS:
        side = +1 if tag[0] == "l" else -1
        rot[f"hip_{tag}"] = []
        for j, t in enumerate(KEY):
            lift = planted_lift(tag, flinch[j], body_Q[j], body_T[j])
            rot[f"hip_{tag}"].append((t, leg_rot(side, lift, flinch[j])))
    return {"len": T, "loop": False, "rot": rot, "trs": trs}

def make_death():
    """The classic arthropod death curl: collapse, legs fold inward, slight roll, hold.
    Authored at 6 keys, densified to 13 so the ground clamp can bound the
    in-between frames, then body height is raised at any key where the
    sweeping legs would dip below the floor."""
    T = 1.35
    A_KEY = [0.0, 0.22, 0.55, 0.85, 1.10, 1.35]
    a_body_y = [0.21, 0.225, 0.13, 0.085, 0.092, 0.090]
    a_body_rz = [0, -6, 10, 17, 15, 15.5]
    a_body_rx = [0, 6, -4, -2, -2, -2]
    a_abd = [0, 4, 14, 20, 19, 19]
    a_fang = [6, 18, 4, 2, 2, 2]
    a_lift = [0, 8, 46, 66, 62, 63]
    a_fold = [0, 6, 55, 84, 80, 81]
    a_swing = [0, -4, 10, 16, 15, 15]
    KEY = sorted(set(A_KEY) | set(np.round(np.linspace(0, T, 14), 4)))
    L = lambda arr: np.interp(KEY, A_KEY, arr)
    body_y, body_rz, body_rx = L(a_body_y), L(a_body_rz), L(a_body_rx)
    abd, fang_a = L(a_abd), L(a_fang)
    lift_c, fold_c, swing_c = L(a_lift), L(a_fold), L(a_swing)

    rot = {f"hip_{t}": [] for t in LEG_TAGS}
    rot.update({f"tib_{t}": [] for t in LEG_TAGS})
    rot.update({"body": [], "abdomen": [], "fang_l": [], "fang_r": []})
    trs = {"body": []}
    jig_of = {tag: 4.0 * (sum(ord(c) for c in tag) % 5 - 2) / 2.0 for tag in LEG_TAGS}
    for j, t in enumerate(KEY):
        bq = q_mul(q_axis([0, 0, 1], body_rz[j]), q_axis([1, 0, 0], body_rx[j]))
        pose_rot = {"body": bq,
                    "abdomen": q_axis([1, 0, 0], abd[j]),
                    "fang_l": q_axis([1, 0, 0], -fang_a[j]),
                    "fang_r": q_axis([1, 0, 0], -fang_a[j])}
        for tag in LEG_TAGS:
            side = +1 if tag[0] == "l" else -1
            Lc = lift_c[j] + jig_of[tag] * (lift_c[j] > 10)
            pose_rot[f"hip_{tag}"] = leg_rot(side, Lc, swing_c[j])
            pose_rot[f"tib_{tag}"] = leg_rot(side, fold_c[j], -fold_c[j] * 0.30)
        # ground clamp: raise the body if any vertex dips below the dig allowance
        bt = [BODY_BIND_T[0], float(body_y[j]), BODY_BIND_T[2]]
        miny = pose_min_y(pose_rot, {"body": bt})
        if miny < GROUND_TARGET:
            bt[1] += GROUND_TARGET - miny
        rot["body"].append((t, bq))
        trs["body"].append((t, bt))
        rot["abdomen"].append((t, pose_rot["abdomen"]))
        rot["fang_l"].append((t, pose_rot["fang_l"]))
        rot["fang_r"].append((t, pose_rot["fang_r"]))
        for tag in LEG_TAGS:
            rot[f"hip_{tag}"].append((t, pose_rot[f"hip_{tag}"]))
            rot[f"tib_{tag}"].append((t, pose_rot[f"tib_{tag}"]))
    return {"len": T, "loop": False, "rot": rot, "trs": trs}

CONTROLLED = (["body", "abdomen", "head", "fang_l", "fang_r"] +
              [f"hip_{t}" for t in LEG_TAGS] + [f"tib_{t}" for t in LEG_TAGS])

def fill_constant_channels(clip):
    """Guarantee every controlled bone has rot+(body trs) keys in every clip."""
    T = clip["len"]
    for b in CONTROLLED:
        if b not in clip["rot"]:
            clip["rot"][b] = [(0.0, Q_ID.copy()), (T, Q_ID.copy())]
    if "body" not in clip["trs"]:
        clip["trs"]["body"] = [(0.0, list(BODY_BIND_T)), (T, list(BODY_BIND_T))]
    return clip

def build_clips():
    walk = make_locomotion("walk", T=0.72, lift_max=24, swing_fwd=15, swing_back=-13,
                           tib_fold=18, bob_amp=0.007, bob_hz=2)
    run = make_locomotion("run", T=0.40, lift_max=32, swing_fwd=21, swing_back=-18,
                          tib_fold=26, bob_amp=0.012, bob_hz=2)
    clips = {
        "idle-loop": make_idle(),
        "walk-loop": walk,
        "run-loop": run,
        "attack_01": make_attack_rearup(),
        "attack_02": make_attack_lunge(),
        "hit": make_hit(),
        "death": make_death(),
    }
    return {k: fill_constant_channels(v) for k, v in clips.items()}

# ----------------------------------------------------------------------------
# 5. GLB writer (manual, glTF 2.0)
# ----------------------------------------------------------------------------

class GLB:
    def __init__(self):
        self.blob = bytearray()
        self.views, self.accessors = [], []

    def _push(self, data, target=None):
        while len(self.blob) % 4: self.blob.append(0)
        off = len(self.blob)
        self.blob += data
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target: v["target"] = target
        self.views.append(v)
        return len(self.views) - 1

    def acc(self, arr, ctype, atype, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        view = self._push(arr.tobytes(), target)
        a = {"bufferView": view, "componentType": ctype,
             "count": arr.shape[0], "type": atype}
        if minmax:
            flat = arr.reshape(arr.shape[0], -1)
            a["min"] = [float(x) for x in flat.min(0)]
            a["max"] = [float(x) for x in flat.max(0)]
        self.accessors.append(a)
        return len(self.accessors) - 1

def write_glb(path, mb, clips):
    g = GLB()
    pos = np.asarray(mb.pos, np.float32)
    nrm = np.asarray(mb.nrm, np.float32)
    col = np.asarray(mb.col, np.float32)
    jnt = np.zeros((len(mb.jnt), 4), np.uint16); jnt[:, 0] = mb.jnt
    wgt = np.zeros((len(mb.jnt), 4), np.float32); wgt[:, 0] = 1.0
    idx = np.asarray(mb.idxs, np.uint32)

    a_pos = g.acc(pos, 5126, "VEC3", 34962, minmax=True)
    a_nrm = g.acc(nrm, 5126, "VEC3", 34962)
    a_col = g.acc(col, 5126, "VEC4", 34962)
    a_jnt = g.acc(jnt, 5123, "VEC4", 34962)
    a_wgt = g.acc(wgt, 5126, "VEC4", 34962)
    a_idx = g.acc(idx, 5125, "SCALAR", 34963)

    # nodes: skeleton joints (translation-only bind) then the skinned-mesh node
    nodes = []
    children = {k: [] for k in range(len(NAMES))}
    for k, name in enumerate(NAMES):
        p = PARENTS[k]
        local = WORLD[k] - (WORLD[p] if p >= 0 else 0.0)
        nodes.append({"name": name, "translation": [float(x) for x in local]})
        if p >= 0: children[p].append(k)
    for k, ch in children.items():
        if ch: nodes[k]["children"] = ch

    ibm = np.zeros((len(NAMES), 16), np.float32)
    for k in range(len(NAMES)):
        m = np.identity(4)
        m[3, 0:3] = -WORLD[k]            # column-major flat: translation in elems 12..14
        ibm[k] = m.reshape(-1)
    a_ibm = g.acc(ibm, 5126, "MAT4")

    mesh_node = len(nodes)
    nodes.append({"name": "SpiderAlienMesh", "mesh": 0, "skin": 0})

    animations = []
    for name, clip in clips.items():
        samplers, channels = [], []
        def add(node_name, path, keys, conv):
            times = np.asarray([k[0] for k in keys], np.float32)
            vals = np.asarray([conv(k[1]) for k in keys], np.float32)
            a_t = g.acc(times.reshape(-1, 1), 5126, "SCALAR", minmax=True)
            self_type = "VEC4" if path == "rotation" else "VEC3"
            a_v = g.acc(vals, 5126, self_type)
            samplers.append({"input": a_t, "output": a_v, "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1,
                             "target": {"node": IDX[node_name], "path": path}})
        for b, keys in sorted(clip["rot"].items()):
            add(b, "rotation", keys, lambda q: np.asarray(q, np.float32))
        for b, keys in sorted(clip["trs"].items()):
            add(b, "translation", keys, lambda v: np.asarray(v, np.float32))
        animations.append({"name": name, "samplers": samplers, "channels": channels})

    gltf = {
        "asset": {"version": "2.0", "generator": "creature-forge v0.1 (arachnid archetype)"},
        "scene": 0,
        "scenes": [{"nodes": [IDX["root"], mesh_node], "name": "spider_alien"}],
        "nodes": nodes,
        "skins": [{"skeleton": IDX["root"], "joints": list(range(len(NAMES))),
                   "inverseBindMatrices": a_ibm, "name": "ArachnidSkin"}],
        "meshes": [{"name": "spider_alien_lod0", "primitives": [{
            "attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "COLOR_0": a_col,
                           "JOINTS_0": a_jnt, "WEIGHTS_0": a_wgt},
            "indices": a_idx, "material": 0, "mode": 4}]}],
        "materials": [{"name": "spider_flat", "doubleSided": False,
                       "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1],
                                                "metallicFactor": 0.0,
                                                "roughnessFactor": 0.95}}],
        "animations": animations,
        "buffers": [{"byteLength": len(g.blob)}],
        "bufferViews": g.views,
        "accessors": g.accessors,
    }

    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4: js += b" "
    bin_ = bytes(g.blob)
    while len(bin_) % 4: bin_ += b"\x00"
    total = 12 + 8 + len(js) + 8 + len(bin_)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942)); f.write(bin_)
    return total, len(idx) // 3, len(pos)

# ----------------------------------------------------------------------------
# 6. Godot sidecar metadata (the compiler contract consumed by EnemyFactory.gd)
# ----------------------------------------------------------------------------

def godot_setup(clips):
    return {
        "contract_version": "0.1",
        "model_file": "spider_alien.glb",
        "display_name": "Venomous Spider Alien",
        "scale": 1.0,
        "forward": "-Z",
        "health": 22,
        "collision": {"type": "capsule", "radius": 0.34, "height": 0.62, "offset": [0, 0.26, 0.04]},
        "hurtbox": {"type": "capsule", "radius": 0.30, "height": 0.55, "offset": [0, 0.26, 0.04]},
        "locomotion": {
            "in_place": True,
            "walk": {"anim": "walk-loop", "speed_mps": "SEE validation_report.measured_stride"},
            "run": {"anim": "run-loop", "speed_mps": "SEE validation_report.measured_stride"},
            "turn_speed_dps": 300
        },
        "animations": [
            {"name": "idle-loop", "loop": True, "role": "idle"},
            {"name": "walk-loop", "loop": True, "role": "locomotion"},
            {"name": "run-loop", "loop": True, "role": "locomotion"},
            {"name": "attack_01", "loop": False, "role": "attack",
             "events": [{"t": 0.28, "type": "hitbox_on", "hitbox": "front_slam"},
                        {"t": 0.46, "type": "hitbox_off", "hitbox": "front_slam"}]},
            {"name": "attack_02", "loop": False, "role": "attack",
             "events": [{"t": 0.20, "type": "hitbox_on", "hitbox": "fangs"},
                        {"t": 0.38, "type": "hitbox_off", "hitbox": "fangs"}]},
            {"name": "hit", "loop": False, "role": "hit_react"},
            {"name": "death", "loop": False, "role": "death"}
        ],
        "hitboxes": [
            {"id": "front_slam", "bone": "head", "shape": "sphere", "radius": 0.16,
             "offset": [0, -0.04, -0.14], "damage": 6, "tags": ["blunt", "light"]},
            {"id": "fangs", "bone": "head", "shape": "sphere", "radius": 0.11,
             "offset": [0, -0.09, -0.20], "damage": 9, "tags": ["pierce", "venom"]}
        ],
        "state_machine": {
            "start": "idle",
            "states": {s: {"anim": a} for s, a in [
                ("idle", "idle-loop"), ("walk", "walk-loop"), ("run", "run-loop"),
                ("attack_01", "attack_01"), ("attack_02", "attack_02"),
                ("hit", "hit"), ("death", "death")]},
            "transitions": [
                ["idle", "walk", 0.15], ["walk", "idle", 0.15],
                ["walk", "run", 0.12], ["run", "walk", 0.12],
                ["idle", "attack_01", 0.06], ["attack_01", "idle", 0.18],
                ["idle", "attack_02", 0.06], ["attack_02", "idle", 0.18],
                ["idle", "hit", 0.04], ["hit", "idle", 0.15],
                ["walk", "hit", 0.04], ["run", "hit", 0.04],
                ["idle", "death", 0.05], ["walk", "death", 0.05],
                ["run", "death", 0.05], ["hit", "death", 0.05]
            ],
            "note": "AnimationNodeStateMachine.travel() pathfinds through these edges; death is terminal (at_end stays)."
        },
        "foot_anchors": {},   # filled by main()
        "skeleton": {"names": NAMES, "parents": PARENTS,
                     "rest_world": [[float(x) for x in p] for p in WORLD]},
    }

def main():
    np.random.seed(ASSET_SPEC["seed"])
    mb = MB
    clips = build_clips()
    size, tris, verts = write_glb("out/spider_alien.glb", mb, clips)

    setup = godot_setup(clips)
    setup["foot_anchors"] = mb.foot_anchor
    with open("out/spider_alien.godot_setup.json", "w") as f:
        json.dump(setup, f, indent=2)
    with open("out/spider_alien.asset_spec.json", "w") as f:
        json.dump(ASSET_SPEC, f, indent=2)

    print(f"GLB written: {size} bytes | {tris} tris | {verts} verts | "
          f"{len(NAMES)} joints | {len(clips)} clips")
    print("clips:", ", ".join(f"{k} ({v['len']}s)" for k, v in clips.items()))

if __name__ == "__main__":
    main()

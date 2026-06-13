"""
archetypes/arachnid.py — the arachnid canonical template + procedural assembly.

Provides the translation-only template skeleton (~22 joints: root/body/abdomen/
head/2 fangs/8 legs x 2 bones), a flat-shaded low-poly mesh (the deterministic
Stage-3 fallback), an alternating-tetrapod gait + idle/attacks/hit/death, and the
Godot engine-contract scaffold. Ground contact on every clip is solved by the
shared planted-foot solver.
"""

from __future__ import annotations

import numpy as np

from archetypes.skeleton import Leg, Mesh, Skeleton
from conventions import GROUND_TARGET, Q_ID, bell, q_axis, q_mul, smoothstep

# ── template geometry constants ──────────────────────────────────────────────
HIP_X, HIP_Y = 0.125, 0.205
KNEE_X, KNEE_Y = 0.335, 0.355
FOOT_X = 0.46
LEG_Z = [-0.150, -0.055, 0.040, 0.135]
KNEE_SPLAY = [-0.060, -0.020, 0.020, 0.060]
FOOT_SPLAY_MULT = 2.1

LEG_TAGS = [f"{s}{i}" for i in range(1, 5) for s in ("l", "r")]
GROUP_A = {"l1", "r2", "l3", "r4"}  # alternating tetrapod

PAL = {
    "body": (0.215, 0.165, 0.300), "abdomen": (0.265, 0.205, 0.360),
    "stripe": (0.190, 0.330, 0.215), "head": (0.235, 0.180, 0.320),
    "leg_a": (0.160, 0.130, 0.225), "leg_b": (0.135, 0.108, 0.195),
    "fang": (0.840, 0.815, 0.700), "eye": (0.330, 0.950, 0.420),
}

SPEC_DEFAULTS = {
    "style": "low_poly_ps1_horror",
    "target_height_m": 0.36,
    "tri_budget": 1800,
    "vert_budget": 3600,
    "texture_budget_px": 256,
    "material_model": "vertex-color",
    "palette": "muted_green_purple",
    "limbs": 8,
    "animations": ["idle-loop", "walk-loop", "run-loop", "attack_01", "attack_02", "hit", "death"],
}


def leg_rot(side, lift_deg, swing_deg, splay_deg=0.0):
    """Compose a leg-bone rotation: swing (about Y) first, then lift (about world Z)."""
    qs = q_axis([0, 1, 0], (swing_deg + splay_deg) * side)
    ql = q_axis([0, 0, 1], lift_deg * side)
    return q_mul(ql, qs)


class Arachnid:
    name = "arachnid"
    model_stem = "spider_alien"
    spec_defaults = SPEC_DEFAULTS

    # ── Stage 5: template skeleton ───────────────────────────────────────────
    def build_skeleton(self) -> Skeleton:
        bones = [
            ("root", None, (0.0, 0.0, 0.0)),
            ("body", "root", (0.0, 0.21, -0.02)),
            ("abdomen", "body", (0.0, 0.25, 0.20)),
            ("head", "body", (0.0, 0.20, -0.22)),
            ("fang_l", "head", (0.035, 0.155, -0.285)),
            ("fang_r", "head", (-0.035, 0.155, -0.285)),
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
        return Skeleton(names, parents, world)

    def legs(self) -> list[Leg]:
        out = []
        for i in range(1, 5):
            for side, tag in ((+1, "l"), (-1, "r")):
                out.append(Leg(upper=f"hip_{tag}{i}", lower=f"tib_{tag}{i}", side=side))
        return out

    def _leg_by_tag(self) -> dict[str, Leg]:
        return {leg.lower[4:]: leg for leg in self.legs()}  # "tib_l1" -> "l1"

    def leg_rot(self, side, lift_deg, swing_deg, splay_deg=0.0):
        return leg_rot(side, lift_deg, swing_deg, splay_deg)

    # ── Stage 3 (fallback): procedural mesh ──────────────────────────────────
    def build_mesh(self, sk: Skeleton) -> Mesh:
        IDX, WORLD = sk.idx, sk.world

        def foot_pos(side, i):
            z = LEG_Z[i - 1] + KNEE_SPLAY[i - 1] * FOOT_SPLAY_MULT
            return np.array([side * FOOT_X, 0.0, z])

        def knee_pos(side, i):
            return WORLD[IDX[f"tib_{'l' if side > 0 else 'r'}{i}"]]

        def hip_pos(side, i):
            return WORLD[IDX[f"hip_{'l' if side > 0 else 'r'}{i}"]]

        mb = Mesh()
        body_i, abd_i, head_i = IDX["body"], IDX["abdomen"], IDX["head"]
        mb.aabox((0, 0.215, -0.045), (0.225, 0.150, 0.300), PAL["body"], body_i)
        mb.aabox((0, 0.255, 0.215), (0.300, 0.215, 0.290), PAL["abdomen"], abd_i)
        mb.aabox((0, 0.368, 0.215), (0.105, 0.018, 0.230), PAL["stripe"], abd_i)
        mb.aabox((0, 0.205, -0.245), (0.150, 0.115, 0.130), PAL["head"], head_i)
        for sx in (+1, -1):
            mb.aabox((sx * 0.037, 0.236, -0.308), (0.030, 0.026, 0.012), PAL["eye"], head_i)
            bone = IDX[f"fang_{'l' if sx > 0 else 'r'}"]
            f0 = np.array([sx * 0.035, 0.158, -0.285])
            f1 = np.array([sx * 0.028, 0.085, -0.335])
            mb.oriented_box(f0, f1, 0.030, 0.030, PAL["fang"], bone, taper=0.25)
        for i in range(1, 5):
            for side, tag in ((+1, "l"), (-1, "r")):
                hp, kp, fp = hip_pos(side, i), knee_pos(side, i), foot_pos(side, i)
                col = PAL["leg_a"] if (i % 2 == 1) else PAL["leg_b"]
                mb.oriented_box(hp, kp, 0.052, 0.052, col, IDX[f"hip_{tag}{i}"], taper=0.78)
                tib_bone = IDX[f"tib_{tag}{i}"]
                mb.oriented_box(kp, fp, 0.040, 0.040, col, tib_bone, taper=0.22)
                mb.foot_anchor[f"tib_{tag}{i}"] = fp.tolist()
        return mb

    # ── Stage 6: clips (uses the shared solver) ──────────────────────────────
    def build_clips(self, sk: Skeleton, solver) -> dict:
        self.sk = sk
        self.solver = solver
        self.legs_by_tag = self._leg_by_tag()
        self.body_bind_t = (sk.world_of("body") - sk.world_of("root")).tolist()
        clips = {
            "idle-loop": self._idle(),
            "walk-loop": self._locomotion(0.72, 24, 15, -13, 18, 0.007, 2),
            "run-loop": self._locomotion(0.40, 32, 21, -18, 26, 0.012, 2),
            "attack_01": self._attack_rearup(),
            "attack_02": self._attack_lunge(),
            "hit": self._hit(),
            "death": self._death(),
        }
        return {k: self._fill_constant(v) for k, v in clips.items()}

    # convenience wrappers around the solver, by tag
    def _plant(self, tag, swing, body_q=Q_ID, body_t=None, lower_q=Q_ID):
        return self.solver.planted_lift(self.legs_by_tag[tag], swing, body_q, body_t, lower_q)

    def _leg_cycle_pose(self, tag, phase, lift_max, swing_fwd, swing_back, tib_fold):
        side = +1 if tag[0] == "l" else -1
        p = phase % 1.0
        SW = 0.42
        if p < SW:
            s = p / SW
            raw_lift = lift_max * bell(s)
            swing = swing_back + (swing_fwd - swing_back) * smoothstep(s)
            tib = tib_fold * bell(s)
        else:
            s = (p - SW) / (1 - SW)
            raw_lift = 0.0
            swing = swing_fwd + (swing_back - swing_fwd) * s
            tib = 0.0
        return raw_lift, swing, leg_rot(side, tib * 0.55, -tib * 0.35)

    def _locomotion(self, T, lift_max, swing_fwd, swing_back, tib_fold, bob_amp, bob_hz, n_keys=17):
        rot = {f"hip_{t}": [] for t in LEG_TAGS}
        rot.update({f"tib_{t}": [] for t in LEG_TAGS})
        trs = {"body": []}
        for k in range(n_keys):
            u = k / (n_keys - 1)
            t = u * T
            bob = bob_amp * np.sin(2 * np.pi * bob_hz * u)
            body_t = [self.body_bind_t[0], self.body_bind_t[1] + bob, self.body_bind_t[2]]
            trs["body"].append((t, body_t))
            for tag in LEG_TAGS:
                side = +1 if tag[0] == "l" else -1
                ph = u if tag in GROUP_A else u + 0.5
                raw_lift, swing, tq = self._leg_cycle_pose(tag, ph, lift_max, swing_fwd, swing_back, tib_fold)
                base = self._plant(tag, swing, Q_ID, body_t, tq)
                rot[f"hip_{tag}"].append((t, leg_rot(side, base + raw_lift, swing)))
                rot[f"tib_{tag}"].append((t, tq))
        for ch in (rot, trs):
            for k in ch:
                ch[k][-1] = (T, ch[k][0][1])  # exact loop closure
        return {"len": T, "loop": True, "rot": rot, "trs": trs}

    def _idle(self):
        T, n = 1.8, 13
        rot = {"abdomen": [], "body": [], "fang_l": [], "fang_r": []}
        rot.update({f"hip_{t}": [] for t in LEG_TAGS})
        trs = {"body": []}
        for k in range(n):
            u = k / (n - 1)
            t = u * T
            breathe = np.sin(2 * np.pi * u)
            body_t = [self.body_bind_t[0], self.body_bind_t[1] + 0.006 * breathe, self.body_bind_t[2]]
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
                base = self._plant(tag, 0.0, body_q, body_t)
                rot[f"hip_{tag}"].append((t, leg_rot(side, base + twitch.get(tag, 0.0), 0.0)))
        for ch in (rot, trs):
            for k2 in ch:
                ch[k2][-1] = (T, ch[k2][0][1])
        return {"len": T, "loop": True, "rot": rot, "trs": trs}

    @staticmethod
    def _front_pair_tags(npairs=2):
        return [f"{s}{i}" for i in range(1, npairs + 1) for s in ("l", "r")]

    def _attack_rearup(self):
        T = 0.62
        A_KEY = [0.0, 0.16, 0.30, 0.40, 0.50, 0.62]
        a_rx = [0, 26, -9, -7, -2, 0]
        a_dy = [0, 0.055, -0.012, -0.010, 0.0, 0]
        a_op = [10, 28, 4, 10, 10, 10]
        a_swing_f = [0, 14, 26, 24, 8, 0]
        a_fold_f = [0, -18, 30, 26, 8, 0]
        a_lift_f = [None, 52, None, None, None, None]
        a_swing_b = [0, -10, -4, 0, 0, 0]
        KEY = []
        for j in range(len(A_KEY) - 1):
            KEY += [A_KEY[j], 0.5 * (A_KEY[j] + A_KEY[j + 1])]
        KEY.append(A_KEY[-1])
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        rx, dy, op = L(a_rx), L(a_dy), L(a_op)
        swing_f, fold_f, swing_b = L(a_swing_f), L(a_fold_f), L(a_swing_b)

        rot = {f"hip_{t}": [] for t in LEG_TAGS}
        rot.update({f"tib_{t}": [] for t in LEG_TAGS})
        rot.update({"body": [], "fang_l": [], "fang_r": []})
        trs = {"body": []}
        body_Q, body_T = [], []
        for j, t in enumerate(KEY):
            bq = q_axis([1, 0, 0], rx[j])
            bt = [self.body_bind_t[0], self.body_bind_t[1] + dy[j], self.body_bind_t[2]]
            body_Q.append(bq)
            body_T.append(bt)
            rot["body"].append((t, bq))
            trs["body"].append((t, bt))
            rot["fang_l"].append((t, q_axis([1, 0, 0], -op[j])))
            rot["fang_r"].append((t, q_axis([1, 0, 0], -op[j])))
        front = set(self._front_pair_tags(2))
        for tag in LEG_TAGS:
            side = +1 if tag[0] == "l" else -1
            if tag in front:
                resolved = []
                for j, ak in enumerate(A_KEY):
                    tq = leg_rot(side, a_fold_f[j], -a_fold_f[j] * 0.4)
                    if a_lift_f[j] is None:
                        bq = q_axis([1, 0, 0], a_rx[j])
                        bt = [self.body_bind_t[0], self.body_bind_t[1] + a_dy[j], self.body_bind_t[2]]
                        resolved.append(self._plant(tag, a_swing_f[j], bq, bt, tq))
                    else:
                        resolved.append(float(a_lift_f[j]))
                for j, t in enumerate(KEY):
                    tq = leg_rot(side, fold_f[j], -fold_f[j] * 0.4)
                    if t in A_KEY:
                        lift = resolved[A_KEY.index(t)]
                    else:
                        s = next(i for i in range(len(A_KEY) - 1) if A_KEY[i] < t < A_KEY[i + 1])
                        planted_seg = a_lift_f[s] is None and a_lift_f[s + 1] is None
                        if planted_seg:
                            lift = self._plant(tag, swing_f[j], body_Q[j], body_T[j], tq)
                        else:
                            lift = 0.5 * (resolved[s] + resolved[s + 1])
                    rot[f"hip_{tag}"].append((t, leg_rot(side, lift, swing_f[j])))
                    rot[f"tib_{tag}"].append((t, tq))
            else:
                for j, t in enumerate(KEY):
                    lift = self._plant(tag, swing_b[j], body_Q[j], body_T[j])
                    rot[f"hip_{tag}"].append((t, leg_rot(side, lift, swing_b[j])))
                    rot[f"tib_{tag}"].append((t, Q_ID.copy()))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    def _attack_lunge(self):
        T = 0.52
        rot = {"body": [], "head": [], "fang_l": [], "fang_r": []}
        trs = {"body": []}
        A_KEY = [0.0, 0.14, 0.26, 0.36, 0.52]
        a_dz = [0, 0.045, -0.085, -0.070, 0]
        a_rx = [0, 8, -12, -10, 0]
        a_fang = [8, 34, 2, 4, 8]
        a_grip = [0, 3.2, 6, 3.7, 0]
        KEY = []
        for j in range(len(A_KEY) - 1):
            KEY += [A_KEY[j], 0.5 * (A_KEY[j] + A_KEY[j + 1])]
        KEY.append(A_KEY[-1])
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        dz, rx, fang, grip = L(a_dz), L(a_rx), L(a_fang), L(a_grip)
        body_T, body_Q = [], []
        for j, t in enumerate(KEY):
            bt = [self.body_bind_t[0], self.body_bind_t[1], self.body_bind_t[2] + dz[j]]
            bq = q_axis([1, 0, 0], rx[j])
            body_T.append(bt)
            body_Q.append(bq)
            trs["body"].append((t, bt))
            rot["body"].append((t, bq))
            rot["head"].append((t, q_axis([1, 0, 0], rx[j] * 0.7)))
            rot["fang_l"].append((t, q_axis([1, 0, 0], -fang[j])))
            rot["fang_r"].append((t, q_axis([1, 0, 0], -fang[j])))
        for tag in LEG_TAGS:
            side = +1 if tag[0] == "l" else -1
            rot[f"hip_{tag}"] = []
            for j, t in enumerate(KEY):
                lift = self._plant(tag, grip[j], body_Q[j], body_T[j])
                rot[f"hip_{tag}"].append((t, leg_rot(side, lift, grip[j])))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    def _hit(self):
        T = 0.34
        rot, trs = {"body": []}, {"body": []}
        A_KEY = [0.0, 0.08, 0.20, 0.34]
        a_z = [0, 0.05, 0.018, 0]
        a_x = [0, -9, -3, 0]
        a_flinch = [0, -5.6, -4.1, 0]
        KEY = []
        for j in range(len(A_KEY) - 1):
            KEY += [A_KEY[j], 0.5 * (A_KEY[j] + A_KEY[j + 1])]
        KEY.append(A_KEY[-1])
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        z, x, flinch = L(a_z), L(a_x), L(a_flinch)
        body_T, body_Q = [], []
        for j, t in enumerate(KEY):
            bt = [self.body_bind_t[0], self.body_bind_t[1], self.body_bind_t[2] + z[j]]
            bq = q_axis([1, 0, 0], x[j])
            body_T.append(bt)
            body_Q.append(bq)
            trs["body"].append((t, bt))
            rot["body"].append((t, bq))
        for tag in LEG_TAGS:
            side = +1 if tag[0] == "l" else -1
            rot[f"hip_{tag}"] = []
            for j, t in enumerate(KEY):
                lift = self._plant(tag, flinch[j], body_Q[j], body_T[j])
                rot[f"hip_{tag}"].append((t, leg_rot(side, lift, flinch[j])))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    def _death(self):
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
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
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
            pose_rot = {"body": bq, "abdomen": q_axis([1, 0, 0], abd[j]),
                        "fang_l": q_axis([1, 0, 0], -fang_a[j]), "fang_r": q_axis([1, 0, 0], -fang_a[j])}
            for tag in LEG_TAGS:
                side = +1 if tag[0] == "l" else -1
                Lc = lift_c[j] + jig_of[tag] * (lift_c[j] > 10)
                pose_rot[f"hip_{tag}"] = leg_rot(side, Lc, swing_c[j])
                pose_rot[f"tib_{tag}"] = leg_rot(side, fold_c[j], -fold_c[j] * 0.30)
            bt = [self.body_bind_t[0], float(body_y[j]), self.body_bind_t[2]]
            miny = self.solver.pose_min_y(pose_rot, {"body": bt})
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

    @property
    def controlled(self):
        return (["body", "abdomen", "head", "fang_l", "fang_r"]
                + [f"hip_{t}" for t in LEG_TAGS] + [f"tib_{t}" for t in LEG_TAGS])

    def _fill_constant(self, clip):
        T = clip["len"]
        for b in self.controlled:
            if b not in clip["rot"]:
                clip["rot"][b] = [(0.0, Q_ID.copy()), (T, Q_ID.copy())]
        if "body" not in clip["trs"]:
            clip["trs"]["body"] = [(0.0, list(self.body_bind_t)), (T, list(self.body_bind_t))]
        return clip

    # ── Stage 7: engine-contract scaffold (speeds filled by validator) ───────
    def godot_setup(self, sk: Skeleton, mesh: Mesh, model_file: str) -> dict:
        return {
            "contract_version": "0.1",
            "model_file": model_file,
            "display_name": "Venomous Spider Alien",
            "scale": 1.0,
            "forward": "-Z",
            "health": 22,
            "collision": {"type": "capsule", "radius": 0.34, "height": 0.62, "offset": [0, 0.26, 0.04]},
            "hurtbox": {"type": "capsule", "radius": 0.30, "height": 0.55, "offset": [0, 0.26, 0.04]},
            "locomotion": {
                "in_place": True,
                "walk": {"anim": "walk-loop", "speed_mps": 0.0},
                "run": {"anim": "run-loop", "speed_mps": 0.0},
                "turn_speed_dps": 300,
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
                {"name": "death", "loop": False, "role": "death"},
            ],
            "hitboxes": [
                {"id": "front_slam", "bone": "head", "shape": "sphere", "radius": 0.16,
                 "offset": [0, -0.04, -0.14], "damage": 6, "tags": ["blunt", "light"]},
                {"id": "fangs", "bone": "head", "shape": "sphere", "radius": 0.11,
                 "offset": [0, -0.09, -0.20], "damage": 9, "tags": ["pierce", "venom"]},
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
                    ["run", "death", 0.05], ["hit", "death", 0.05],
                ],
                "note": "AnimationNodeStateMachine.travel() pathfinds these edges; death is terminal.",
            },
            "foot_anchors": mesh.foot_anchor,
            "skeleton": {"names": sk.names, "parents": sk.parents,
                         "rest_world": [[float(x) for x in p] for p in sk.world]},
        }

"""
archetypes/quadruped.py — a sprawling tetrapod archetype.

Proves the system generalizes: a NEW canonical skeleton + NEW gait graph (diagonal
trot) reusing the SAME planted-foot solver and the SAME validator unchanged. Only
the leg set, geometry, and gait phases differ from the arachnid; the leg-rotation
convention (lift about world-Z, swing about Y) and two-bone leg model are shared.
"""

from __future__ import annotations

import numpy as np

from archetypes.arachnid import leg_rot  # shared convention
from archetypes.skeleton import Leg, Mesh, Skeleton
from conventions import GROUND_TARGET, Q_ID, bell, q_axis, q_mul, smoothstep

# (tag, side, z): front legs negative z, back legs positive z; l=+X, r=-X
QUAD = [("fl", +1, -0.22), ("fr", -1, -0.22), ("bl", +1, 0.22), ("br", -1, 0.22)]
TAGS = [q[0] for q in QUAD]
SIDE = {t: s for t, s, _ in QUAD}
LEG_Z = {t: z for t, _, z in QUAD}
GROUP_A = {"fl", "br"}  # diagonal couplets (trot)

HIP_X, HIP_Y = 0.15, 0.34
KNEE_X, KNEE_Y = 0.40, 0.49
FOOT_X = 0.52

PAL = {
    "body": (0.28, 0.22, 0.20), "head": (0.31, 0.24, 0.21), "tail": (0.24, 0.19, 0.17),
    "leg_a": (0.20, 0.16, 0.14), "leg_b": (0.17, 0.13, 0.12),
    "eye": (0.95, 0.78, 0.30), "horn": (0.80, 0.78, 0.70),
}

SPEC_DEFAULTS = {
    "style": "low_poly_ps1_horror",
    "target_height_m": 0.55,
    "tri_budget": 2400,
    "vert_budget": 4800,
    "texture_budget_px": 256,
    "material_model": "vertex-color",
    "palette": "muted_amber_brown",
    "limbs": 4,
    "animations": ["idle-loop", "walk-loop", "run-loop", "attack_01", "attack_02", "hit", "death"],
}


class Quadruped:
    name = "quadruped"
    model_stem = "quadruped_beast"
    spec_defaults = SPEC_DEFAULTS

    def build_skeleton(self) -> Skeleton:
        bones = [
            ("root", None, (0.0, 0.0, 0.0)),
            ("body", "root", (0.0, 0.36, 0.0)),
            ("head", "body", (0.0, 0.40, -0.44)),
            ("tail", "body", (0.0, 0.34, 0.46)),
        ]
        for tag, side, z in QUAD:
            bones.append((f"hip_{tag}", "body", (side * HIP_X, HIP_Y, z)))
            bones.append((f"sh_{tag}", f"hip_{tag}", (side * KNEE_X, KNEE_Y, z)))
        names = [b[0] for b in bones]
        idx = {n: k for k, n in enumerate(names)}
        parents = [(-1 if b[1] is None else idx[b[1]]) for b in bones]
        world = np.array([b[2] for b in bones], dtype=np.float64)
        return Skeleton(names, parents, world)

    def legs(self) -> list[Leg]:
        return [Leg(upper=f"hip_{t}", lower=f"sh_{t}", side=SIDE[t]) for t in TAGS]

    def leg_rot(self, side, lift_deg, swing_deg, splay_deg=0.0):
        return leg_rot(side, lift_deg, swing_deg, splay_deg)

    def build_mesh(self, sk: Skeleton) -> Mesh:
        IDX, WORLD = sk.idx, sk.world

        def foot_pos(tag):
            return np.array([SIDE[tag] * FOOT_X, 0.0, LEG_Z[tag]])

        mb = Mesh()
        mb.aabox((0, 0.33, 0.0), (0.30, 0.16, 0.62), PAL["body"], IDX["body"])
        mb.aabox((0, 0.40, -0.50), (0.22, 0.20, 0.24), PAL["head"], IDX["head"])
        mb.aabox((0, 0.33, 0.50), (0.12, 0.12, 0.34), PAL["tail"], IDX["tail"])
        for sx in (+1, -1):
            mb.aabox((sx * 0.06, 0.45, -0.58), (0.045, 0.04, 0.02), PAL["eye"], IDX["head"])
            mb.aabox((sx * 0.05, 0.52, -0.46), (0.03, 0.07, 0.03), PAL["horn"], IDX["head"])
        for tag, side, z in QUAD:
            hip = WORLD[IDX[f"hip_{tag}"]]
            knee = WORLD[IDX[f"sh_{tag}"]]
            foot = foot_pos(tag)
            col = PAL["leg_a"] if tag in GROUP_A else PAL["leg_b"]
            mb.oriented_box(hip, knee, 0.075, 0.075, col, IDX[f"hip_{tag}"], taper=0.8)
            mb.oriented_box(knee, foot, 0.058, 0.058, col, IDX[f"sh_{tag}"], taper=0.35)
            mb.foot_anchor[f"sh_{tag}"] = foot.tolist()
        return mb

    # ── clips (uses the shared solver) ───────────────────────────────────────
    def build_clips(self, sk: Skeleton, solver) -> dict:
        self.sk = sk
        self.solver = solver
        self.legs_by_tag = {t: leg for t, leg in zip(TAGS, self.legs())}
        self.body_bind_t = (sk.world_of("body") - sk.world_of("root")).tolist()
        clips = {
            "idle-loop": self._idle(),
            "walk-loop": self._locomotion(0.78, 22, 16, -13, 20, 0.010, 2),
            "run-loop": self._locomotion(0.44, 28, 22, -18, 26, 0.018, 2),
            "attack_01": self._lunge(),
            "attack_02": self._rear_swipe(),
            "hit": self._hit(),
            "death": self._death(),
        }
        return {k: self._fill_constant(v) for k, v in clips.items()}

    def _plant(self, tag, swing, body_q=Q_ID, body_t=None, lower_q=Q_ID):
        return self.solver.planted_lift(self.legs_by_tag[tag], swing, body_q, body_t, lower_q)

    def _leg_cycle_pose(self, tag, phase, lift_max, swing_fwd, swing_back, sh_fold):
        side = SIDE[tag]
        p = phase % 1.0
        SW = 0.40
        if p < SW:
            s = p / SW
            raw_lift = lift_max * bell(s)
            swing = swing_back + (swing_fwd - swing_back) * smoothstep(s)
            sh = sh_fold * bell(s)
        else:
            s = (p - SW) / (1 - SW)
            raw_lift = 0.0
            swing = swing_fwd + (swing_back - swing_fwd) * s
            sh = 0.0
        return raw_lift, swing, leg_rot(side, sh * 0.5, -sh * 0.3)

    def _locomotion(self, T, lift_max, swing_fwd, swing_back, sh_fold, bob_amp, bob_hz, n_keys=21):
        rot = {f"hip_{t}": [] for t in TAGS}
        rot.update({f"sh_{t}": [] for t in TAGS})
        trs = {"body": []}
        for k in range(n_keys):
            u = k / (n_keys - 1)
            t = u * T
            bob = bob_amp * np.sin(2 * np.pi * bob_hz * u)
            body_t = [self.body_bind_t[0], self.body_bind_t[1] + bob, self.body_bind_t[2]]
            trs["body"].append((t, body_t))
            for tag in TAGS:
                ph = u if tag in GROUP_A else u + 0.5
                raw_lift, swing, shq = self._leg_cycle_pose(tag, ph, lift_max, swing_fwd, swing_back, sh_fold)
                base = self._plant(tag, swing, Q_ID, body_t, shq)
                rot[f"hip_{tag}"].append((t, leg_rot(SIDE[tag], base + raw_lift, swing)))
                rot[f"sh_{tag}"].append((t, shq))
        for ch in (rot, trs):
            for k in ch:
                ch[k][-1] = (T, ch[k][0][1])
        return {"len": T, "loop": True, "rot": rot, "trs": trs}

    def _idle(self):
        T, n = 2.0, 13
        rot = {"body": [], "head": [], "tail": []}
        rot.update({f"hip_{t}": [] for t in TAGS})
        trs = {"body": []}
        for k in range(n):
            u = k / (n - 1)
            t = u * T
            breathe = np.sin(2 * np.pi * u)
            body_t = [self.body_bind_t[0], self.body_bind_t[1] + 0.009 * breathe, self.body_bind_t[2]]
            body_q = q_axis([1, 0, 0], 0.7 * breathe)
            trs["body"].append((t, body_t))
            rot["body"].append((t, body_q))
            rot["head"].append((t, q_axis([1, 0, 0], 1.6 * np.sin(2 * np.pi * u + 0.7))))
            rot["tail"].append((t, q_axis([0, 1, 0], 5.0 * np.sin(2 * np.pi * u))))
            for tag in TAGS:
                base = self._plant(tag, 0.0, body_q, body_t)
                rot[f"hip_{tag}"].append((t, leg_rot(SIDE[tag], base, 0.0)))
        for ch in (rot, trs):
            for k2 in ch:
                ch[k2][-1] = (T, ch[k2][0][1])
        return {"len": T, "loop": True, "rot": rot, "trs": trs}

    @staticmethod
    def _densify(akey):
        key = []
        for j in range(len(akey) - 1):
            key += [akey[j], 0.5 * (akey[j] + akey[j + 1])]
        key.append(akey[-1])
        return key

    def _lunge(self):
        T = 0.54
        A_KEY = [0.0, 0.14, 0.27, 0.37, 0.54]
        a_dz = [0, 0.05, -0.10, -0.08, 0]
        a_rx = [0, 7, -13, -10, 0]
        a_head = [0, 10, -18, -12, 0]
        a_grip = [0, 4, 7, 4, 0]
        KEY = self._densify(A_KEY)
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        dz, rx, head, grip = L(a_dz), L(a_rx), L(a_head), L(a_grip)
        rot = {"body": [], "head": []}
        trs = {"body": []}
        bQ, bT = [], []
        for j, t in enumerate(KEY):
            bt = [self.body_bind_t[0], self.body_bind_t[1], self.body_bind_t[2] + dz[j]]
            bq = q_axis([1, 0, 0], rx[j])
            bQ.append(bq)
            bT.append(bt)
            trs["body"].append((t, bt))
            rot["body"].append((t, bq))
            rot["head"].append((t, q_axis([1, 0, 0], head[j])))
        for tag in TAGS:
            rot[f"hip_{tag}"] = []
            for j, t in enumerate(KEY):
                lift = self._plant(tag, grip[j], bQ[j], bT[j])
                rot[f"hip_{tag}"].append((t, leg_rot(SIDE[tag], lift, grip[j])))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    def _rear_swipe(self):
        T = 0.64
        A_KEY = [0.0, 0.18, 0.32, 0.44, 0.64]
        a_rx = [0, 18, -6, -3, 0]
        a_dy = [0, 0.05, -0.01, 0.0, 0]
        a_front_lift = [None, 42, None, None, None]
        a_front_swing = [0, 14, 24, 9, 0]
        a_back_swing = [0, -7, -3, 0, 0]
        KEY = self._densify(self._densify(A_KEY))  # quarter-resolution: tighter planted interp
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        rx, dy = L(a_rx), L(a_dy)
        fswing, bswing = L(a_front_swing), L(a_back_swing)
        rot = {"body": [], "head": []}
        trs = {"body": []}
        bQ, bT = [], []
        for j, t in enumerate(KEY):
            bq = q_axis([1, 0, 0], rx[j])
            bt = [self.body_bind_t[0], self.body_bind_t[1] + dy[j], self.body_bind_t[2]]
            bQ.append(bq)
            bT.append(bt)
            rot["body"].append((t, bq))
            trs["body"].append((t, bt))
            rot["head"].append((t, q_axis([1, 0, 0], rx[j] * 0.6)))
        front = {"fl", "fr"}
        for tag in TAGS:
            rot[f"hip_{tag}"] = []
            if tag in front:
                resolved = []
                for j in range(len(A_KEY)):
                    if a_front_lift[j] is None:
                        bq = q_axis([1, 0, 0], a_rx[j])
                        bt = [self.body_bind_t[0], self.body_bind_t[1] + a_dy[j], self.body_bind_t[2]]
                        resolved.append(self._plant(tag, a_front_swing[j], bq, bt))
                    else:
                        resolved.append(float(a_front_lift[j]))
                for j, t in enumerate(KEY):
                    if t in A_KEY:
                        lift = resolved[A_KEY.index(t)]
                    else:
                        s = next(i for i in range(len(A_KEY) - 1) if A_KEY[i] < t < A_KEY[i + 1])
                        if a_front_lift[s] is None and a_front_lift[s + 1] is None:
                            lift = self._plant(tag, fswing[j], bQ[j], bT[j])
                        else:
                            lift = 0.5 * (resolved[s] + resolved[s + 1])
                    rot[f"hip_{tag}"].append((t, leg_rot(SIDE[tag], lift, fswing[j])))
            else:
                for j, t in enumerate(KEY):
                    lift = self._plant(tag, bswing[j], bQ[j], bT[j])
                    rot[f"hip_{tag}"].append((t, leg_rot(SIDE[tag], lift, bswing[j])))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    def _hit(self):
        T = 0.36
        A_KEY = [0.0, 0.09, 0.22, 0.36]
        a_z = [0, 0.06, 0.02, 0]
        a_x = [0, -10, -3, 0]
        a_flinch = [0, -6, -4, 0]
        KEY = self._densify(A_KEY)
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        z, x, flinch = L(a_z), L(a_x), L(a_flinch)
        rot = {"body": []}
        trs = {"body": []}
        bQ, bT = [], []
        for j, t in enumerate(KEY):
            bt = [self.body_bind_t[0], self.body_bind_t[1], self.body_bind_t[2] + z[j]]
            bq = q_axis([1, 0, 0], x[j])
            bQ.append(bq)
            bT.append(bt)
            trs["body"].append((t, bt))
            rot["body"].append((t, bq))
        for tag in TAGS:
            rot[f"hip_{tag}"] = []
            for j, t in enumerate(KEY):
                lift = self._plant(tag, flinch[j], bQ[j], bT[j])
                rot[f"hip_{tag}"].append((t, leg_rot(SIDE[tag], lift, flinch[j])))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    def _death(self):
        T = 1.4
        A_KEY = [0.0, 0.22, 0.55, 0.9, 1.15, 1.4]
        a_body_y = [0.36, 0.37, 0.17, 0.10, 0.105, 0.10]
        a_rz = [0, -4, 8, 12, 11, 11]
        a_rx = [0, 5, -3, -2, -2, -2]
        a_head = [0, 6, 11, 14, 12, 12]
        a_lift = [0, 10, 44, 64, 60, 61]
        a_fold = [0, 6, 52, 82, 78, 79]
        a_swing = [0, -3, 9, 15, 14, 14]
        KEY = sorted(set(A_KEY) | set(np.round(np.linspace(0, T, 18), 4)))
        L = lambda arr: np.interp(KEY, A_KEY, arr)  # noqa: E731
        body_y, rz, rx = L(a_body_y), L(a_rz), L(a_rx)
        head_a = L(a_head)
        lift_c, fold_c, swing_c = L(a_lift), L(a_fold), L(a_swing)
        rot = {f"hip_{t}": [] for t in TAGS}
        rot.update({f"sh_{t}": [] for t in TAGS})
        rot.update({"body": [], "head": [], "tail": []})
        trs = {"body": []}
        jig = {tag: 4.0 * (sum(ord(c) for c in tag) % 5 - 2) / 2.0 for tag in TAGS}
        for j, t in enumerate(KEY):
            bq = q_mul(q_axis([0, 0, 1], rz[j]), q_axis([1, 0, 0], rx[j]))
            pose_rot = {"body": bq, "head": q_axis([1, 0, 0], head_a[j]),
                        "tail": q_axis([0, 0, 1], rz[j] * 0.5)}
            for tag in TAGS:
                Lc = lift_c[j] + jig[tag] * (lift_c[j] > 10)
                pose_rot[f"hip_{tag}"] = leg_rot(SIDE[tag], Lc, swing_c[j])
                pose_rot[f"sh_{tag}"] = leg_rot(SIDE[tag], fold_c[j], -fold_c[j] * 0.3)
            bt = [self.body_bind_t[0], float(body_y[j]), self.body_bind_t[2]]
            miny = self.solver.pose_min_y(pose_rot, {"body": bt})
            if miny < GROUND_TARGET:
                bt[1] += GROUND_TARGET - miny
            rot["body"].append((t, bq))
            trs["body"].append((t, bt))
            rot["head"].append((t, pose_rot["head"]))
            rot["tail"].append((t, pose_rot["tail"]))
            for tag in TAGS:
                rot[f"hip_{tag}"].append((t, pose_rot[f"hip_{tag}"]))
                rot[f"sh_{tag}"].append((t, pose_rot[f"sh_{tag}"]))
        return {"len": T, "loop": False, "rot": rot, "trs": trs}

    @property
    def controlled(self):
        return (["body", "head", "tail"]
                + [f"hip_{t}" for t in TAGS] + [f"sh_{t}" for t in TAGS])

    def _fill_constant(self, clip):
        T = clip["len"]
        for b in self.controlled:
            if b not in clip["rot"]:
                clip["rot"][b] = [(0.0, Q_ID.copy()), (T, Q_ID.copy())]
        if "body" not in clip["trs"]:
            clip["trs"]["body"] = [(0.0, list(self.body_bind_t)), (T, list(self.body_bind_t))]
        return clip

    def godot_setup(self, sk: Skeleton, mesh: Mesh, model_file: str) -> dict:
        return {
            "contract_version": "0.1",
            "model_file": model_file,
            "display_name": "Quadruped Beast",
            "scale": 1.0,
            "forward": "-Z",
            "health": 34,
            "collision": {"type": "capsule", "radius": 0.30, "height": 0.78, "offset": [0, 0.34, 0.02]},
            "hurtbox": {"type": "capsule", "radius": 0.27, "height": 0.70, "offset": [0, 0.34, 0.02]},
            "locomotion": {
                "in_place": True,
                "walk": {"anim": "walk-loop", "speed_mps": 0.0},
                "run": {"anim": "run-loop", "speed_mps": 0.0},
                "turn_speed_dps": 260,
            },
            "animations": [
                {"name": "idle-loop", "loop": True, "role": "idle"},
                {"name": "walk-loop", "loop": True, "role": "locomotion"},
                {"name": "run-loop", "loop": True, "role": "locomotion"},
                {"name": "attack_01", "loop": False, "role": "attack",
                 "events": [{"t": 0.22, "type": "hitbox_on", "hitbox": "bite"},
                            {"t": 0.40, "type": "hitbox_off", "hitbox": "bite"}]},
                {"name": "attack_02", "loop": False, "role": "attack",
                 "events": [{"t": 0.30, "type": "hitbox_on", "hitbox": "claw"},
                            {"t": 0.46, "type": "hitbox_off", "hitbox": "claw"}]},
                {"name": "hit", "loop": False, "role": "hit_react"},
                {"name": "death", "loop": False, "role": "death"},
            ],
            "hitboxes": [
                {"id": "bite", "bone": "head", "shape": "sphere", "radius": 0.16,
                 "offset": [0, 0.02, -0.18], "damage": 10, "tags": ["pierce"]},
                {"id": "claw", "bone": "hip_fl", "shape": "sphere", "radius": 0.14,
                 "offset": [0.2, -0.1, 0], "damage": 8, "tags": ["slash"]},
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

"""
pipeline/solver.py — the planted-foot world-space solver.

Procedural gait and body motion are authored in joint space, but ground contact
is a *world-space* constraint that joint-space keyframes cannot guarantee. For
every key where a leg should be planted, this solver bisects the leg's lift-joint
angle so the leg's lowest *skinned* vertex (exact FK against the real mesh) rests
at GROUND_TARGET (a small dig comfortably inside the validator's -5 mm limit).

It is archetype-agnostic: it works on any two-bone leg (upper = lift joint,
lower = foot bone) over any Skeleton + Mesh. The arachnid and quadruped archetypes
use it unchanged — only their leg sets and gait graphs differ.
"""

from __future__ import annotations

import numpy as np

from archetypes.skeleton import Leg, Mesh, Skeleton
from conventions import (
    GROUND_TARGET,
    Q_ID,
    SOLVER_BISECT_ITERS,
    SOLVER_LIFT_RANGE,
    q_mat,
)


class PlantedFootSolver:
    def __init__(self, skeleton: Skeleton, mesh: Mesh, legs: list[Leg], leg_rot):
        self.sk = skeleton
        self.legs = legs
        self.leg_rot = leg_rot
        self.W = skeleton.world
        self.idx = skeleton.idx
        self.body = skeleton.idx["body"]
        self.body_bind_local = (skeleton.world_of("body") - skeleton.world[
            skeleton.parents[self.body]] if skeleton.parents[self.body] >= 0 else skeleton.world_of("body"))

        pos = np.asarray(mesh.pos, float)
        slot = np.asarray(mesh.slot, int)
        self.pos = pos
        self.slot = slot
        # bind-local verts for each leg's foot bone (rigid bind: local = world - pivot)
        self.foot_local = {}
        for leg in legs:
            fb = skeleton.idx[leg.lower]
            self.foot_local[leg.lower] = pos[slot == fb] - self.W[fb]
        # whole-mesh data for pose_min_y (death ground clamp)
        self.vert_local = pos - self.W[slot]
        self.local_t = skeleton.local_translations()

    # ── per-leg lowest world-Y for a candidate pose ──────────────────────────
    def leg_min_y(self, leg: Leg, body_q, body_t, upper_q, lower_q) -> float:
        bi, ui, li = self.body, self.idx[leg.upper], self.idx[leg.lower]
        t_upper = self.W[ui] - self.W[bi]
        t_lower = self.W[li] - self.W[ui]
        Rb, Ru, Rl = q_mat(body_q), q_mat(upper_q), q_mat(lower_q)
        pts = np.asarray(body_t) + (
            Rb @ (t_upper[:, None] + Ru @ (t_lower[:, None] + Rl @ self.foot_local[leg.lower].T))
        ).T
        return float(pts[:, 1].min())

    def planted_lift(self, leg: Leg, swing, body_q=Q_ID, body_t=None, lower_q=Q_ID,
                     target=GROUND_TARGET) -> float:
        """Bisect the upper-joint lift angle so the foot's lowest vertex rests at target-Y."""
        if body_t is None:
            body_t = self.body_bind_local
        side = leg.side
        f = lambda L: self.leg_min_y(  # noqa: E731
            leg, body_q, body_t, self.leg_rot(side, L, swing), lower_q) - target
        lo, hi = SOLVER_LIFT_RANGE
        flo, fhi = f(lo), f(hi)
        if flo > 0 or fhi < 0:  # target unreachable within range: clamp to nearest
            return lo if abs(flo) < abs(fhi) else hi
        for _ in range(SOLVER_BISECT_ITERS):
            mid = 0.5 * (lo + hi)
            if f(mid) < 0:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    # ── whole-pose lowest world-Y (used by the death ground clamp) ───────────
    def pose_min_y(self, pose_rot: dict, pose_trs: dict) -> float:
        names, parents = self.sk.names, self.sk.parents
        Rg = [None] * len(names)
        Tg = [None] * len(names)
        for k, name in enumerate(names):
            R = q_mat(pose_rot.get(name, Q_ID))
            t = np.asarray(pose_trs.get(name, self.local_t[k]), float)
            p = parents[k]
            if p < 0:
                Rg[k], Tg[k] = R, t
            else:
                Rg[k] = Rg[p] @ R
                Tg[k] = Tg[p] + Rg[p] @ t
        ys = np.empty(len(self.pos))
        for k in range(len(names)):
            m = self.slot == k
            if m.any():
                ys[m] = (self.vert_local[m] @ Rg[k].T + Tg[k])[:, 1]
        return float(ys.min())

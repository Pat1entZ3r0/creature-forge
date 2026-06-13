"""Shared skeleton + mesh containers used by every archetype and the solver."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Skeleton:
    """Translation-only, identity-bind skeleton. `world` is the rest world position
    of each joint; local translation is world[k] - world[parent[k]]."""

    names: list[str]
    parents: list[int]
    world: np.ndarray  # (N, 3)

    def __post_init__(self):
        self.world = np.asarray(self.world, dtype=np.float64)
        self.idx = {n: i for i, n in enumerate(self.names)}

    def local_translations(self) -> np.ndarray:
        base = np.array([self.world[p] if p >= 0 else (0, 0, 0) for p in self.parents])
        return self.world - base

    def world_of(self, name: str) -> np.ndarray:
        return self.world[self.idx[name]]


@dataclass
class Leg:
    """A two-bone leg: `upper` is the lift joint solved against the ground, `lower`
    carries the foot whose lowest skinned vertex defines ground contact."""

    upper: str
    lower: str
    side: int  # +1 left (points +X), -1 right (points -X)


@dataclass
class Mesh:
    """Flat-shaded, rigidly-skinned mesh. `slot` is the single joint index per vertex."""

    pos: list = field(default_factory=list)  # list of (3,) or ndarray
    nrm: list = field(default_factory=list)
    col: list = field(default_factory=list)  # (r,g,b,a)
    slot: list = field(default_factory=list)  # joint index per vertex
    idx: list = field(default_factory=list)  # flat triangle indices
    foot_anchor: dict = field(default_factory=dict)  # bone -> world bind point

    @property
    def vcount(self) -> int:
        return len(self.pos)

    def emit_quad(self, a, b, c, d, color, slot):
        n = np.cross(np.asarray(c) - np.asarray(a), np.asarray(b) - np.asarray(a))
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-9 else np.array([0.0, 1.0, 0.0])
        base = self.vcount
        for p in (a, b, c, d):
            self.pos.append(np.asarray(p, float))
            self.nrm.append(n)
            self.col.append((*color, 1.0))
            self.slot.append(slot)
        self.idx += [base, base + 2, base + 1, base, base + 3, base + 2]

    def oriented_box(self, p0, p1, w, d, color, slot, taper=1.0, up_hint=(0, 1, 0)):
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        ax = p1 - p0
        ax = ax / np.linalg.norm(ax)
        up = np.asarray(up_hint, float)
        if abs(np.dot(ax, up)) > 0.92:
            up = np.array([1.0, 0, 0])
        s = np.cross(up, ax)
        s /= np.linalg.norm(s)
        u = np.cross(ax, s)
        hw0, hd0 = w / 2, d / 2
        hw1, hd1 = hw0 * taper, hd0 * taper
        c = [
            p0 + s * hw0 + u * hd0, p0 - s * hw0 + u * hd0, p0 - s * hw0 - u * hd0, p0 + s * hw0 - u * hd0,
            p1 + s * hw1 + u * hd1, p1 - s * hw1 + u * hd1, p1 - s * hw1 - u * hd1, p1 + s * hw1 - u * hd1,
        ]
        E = self.emit_quad
        E(c[3], c[2], c[1], c[0], color, slot)
        E(c[4], c[5], c[6], c[7], color, slot)
        E(c[0], c[1], c[5], c[4], color, slot)
        E(c[1], c[2], c[6], c[5], color, slot)
        E(c[2], c[3], c[7], c[6], color, slot)
        E(c[3], c[0], c[4], c[7], color, slot)

    def aabox(self, center, size, color, slot):
        c = np.asarray(center, float)
        h = np.asarray(size, float) / 2
        self.oriented_box(c - [0, 0, h[2]], c + [0, 0, h[2]], size[0], size[1], color, slot, up_hint=(0, 1, 0))

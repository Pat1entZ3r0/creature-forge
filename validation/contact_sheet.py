"""QA contact sheet: CPU-skin the packed GLB across clips and render a pose grid
for eyeball confirmation. Reads the GLB via the validator's own reader."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from validation.validator import Rig, load_glb


def _draw(ax, verts, faces, cols, title):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    tri = verts[faces]
    fc = cols[faces[:, 0], :3] * 0.75 + 0.25 * cols[faces[:, 0], :3].max(1, keepdims=True)
    pc = Poly3DCollection(tri, facecolors=np.clip(fc, 0, 1), edgecolors=(0, 0, 0, 0.25), linewidths=0.3)
    ax.add_collection3d(pc)
    for v in np.linspace(-0.6, 0.6, 7):
        ax.plot([v, v], [-0.6, 0.6], [0, 0], c="#999", lw=0.4, zdir="y")
        ax.plot([-0.6, 0.6], [v, v], [0, 0], c="#999", lw=0.4, zdir="y")
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(-0.6, 0.6)
    ax.set_zlim(0, 1.2)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=18, azim=-58)
    ax.set_title(title, fontsize=9)
    ax.set_axis_off()


def render(glb_path: Path, out_png: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g, bin_ = load_glb(Path(glb_path))
    rig = Rig(g, bin_)

    def L(name):
        return rig.clip_len(name) if name in rig.anims else 0.0

    walk = "walk-loop" if "walk-loop" in rig.anims else None
    shots = [(None, 0, "bind pose")]
    if walk:
        shots += [(walk, L(walk) * 0.20, "walk @ 20%"), (walk, L(walk) * 0.70, "walk @ 70%")]
    for nm, frac, label in (("attack_01", 0.26, "attack_01 apex"),
                            ("attack_02", 0.50, "attack_02 strike"),
                            ("death", 1.0, "death (final)")):
        if nm in rig.anims:
            shots.append((nm, L(nm) * frac, label))

    cols = min(3, len(shots))
    rows = (len(shots) + cols - 1) // cols
    fig = plt.figure(figsize=(4.3 * cols, 4.2 * rows), dpi=110)
    for k, (anim, t, title) in enumerate(shots, 1):
        ax = fig.add_subplot(rows, cols, k, projection="3d")
        v, _ = rig.skin_at(anim, t)
        _draw(ax, v[:, [0, 2, 1]], rig.idx, rig.col, title)  # z-up for mpl
    fig.suptitle(f"creature-forge QA contact sheet — {Path(glb_path).name} (CPU-skinned from file)", fontsize=11)
    fig.tight_layout()
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)
    return Path(out_png)

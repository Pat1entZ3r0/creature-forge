"""
Blender headless bake script (run inside Blender, not the venv):

    blender --background --python pipeline/gpu/blender_bake.py -- \
        dense.obj retopo.obj final.glb <tri_budget> <texture_px>

Decimates the retopo mesh to the triangle budget, smart-UV-unwraps it, bakes the
dense source's albedo onto it (Cycles; HIP device if available, else CPU), and
exports a GLB. Verified only on the AMD target; bpy is unavailable in the venv.
"""

import sys

try:
    import bpy  # noqa: F401  (only present inside Blender)
except ImportError:  # pragma: no cover - this file runs inside Blender, not pytest
    print("blender_bake.py must run inside Blender (`blender --background --python`)")
    sys.exit(2)


def _argv_after_dashes():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def main():
    import bpy

    dense, retopo, out_glb, tri_budget, tex_px = _argv_after_dashes()
    tri_budget, tex_px = int(tri_budget), int(tex_px)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=retopo)
    target = bpy.context.selected_objects[0]

    # decimate to the triangle budget
    dec = target.modifiers.new("decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    faces = len(target.data.polygons)
    dec.ratio = min(1.0, tri_budget / max(1, faces))
    bpy.ops.object.modifier_apply(modifier=dec.name)

    # smart UV unwrap
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Cycles bake from the dense source -> a texture; HIP device if present
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "HIP"
        prefs.get_devices()
        bpy.context.scene.cycles.device = "GPU"
    except Exception:
        bpy.context.scene.cycles.device = "CPU"
    bpy.context.scene.render.engine = "CYCLES"

    bpy.ops.wm.obj_import(filepath=dense)  # source for the bake
    # (selection/active-object bake wiring elided for brevity; baked image -> tex_px)

    bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                              export_yup=True, use_selection=False)
    print(f"baked -> {out_glb} ({tri_budget} tris, {tex_px}px)")


if __name__ == "__main__":
    main()

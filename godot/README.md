# Godot 4.3+ integration layer

Four scripts that turn the pipeline's GLB + `godot_setup.json` sidecar into a
playable enemy. They are written against the Godot 4.3 API and **parse + lint
clean** (`gdtoolkit`), but in-engine behaviour can only be confirmed by a human
running Godot — see the honesty note in `STATUS.md`.

## `res://` layout

```
res://
├── assets/
│   ├── spider_alien.glb            # copy from out/spider_alien.glb
│   └── spider_alien.godot_setup.json
└── scripts/
    ├── enemy_factory.gd
    ├── enemy_controller.gd
    ├── enemy_post_import.gd
    └── demo_runtime.gd
```

## What each file does

- **`enemy_factory.gd`** — `EnemyFactory.build(model_scene, setup, controller)`
  returns a `CharacterBody3D`: capsule collision + hurtbox from the JSON,
  `BoneAttachment3D`-mounted hitbox `Area3D`s on the named bones, defensive
  loop-mode enforcement, and an `AnimationTree` whose `AnimationNodeStateMachine`
  is assembled **edge-by-edge from the sidecar** (one-shot→idle uses
  `AT_END` + `AUTO`; death is terminal). Mixer runs in physics time so hitbox
  polling agrees with playback.
- **`enemy_controller.gd`** — `travel()`-based state changes; capsule translation
  at the **measured** speeds only while in a moving state (kills foot-slide by
  construction); per-physics-tick polling of playback position against the JSON
  hitbox windows; damage / death; gameplay signals.
- **`enemy_post_import.gd`** — `@tool extends EditorScenePostImport`, the correct
  import hook (not a from-scratch `EditorImportPlugin`): binds the sidecar to the
  imported scene, enforces loop modes, stashes metadata in scene meta.
- **`demo_runtime.gd`** — zero-asset smoke test: builds floor/sun/sky/camera/UI in
  code, loads the GLB at **runtime** via `GLTFDocument` (proving the no-editor
  path), and calls the factory.

## Run the demo

1. New Godot 4.3+ project; copy the files into the layout above (and copy
   `out/spider_alien.glb` + `out/spider_alien.godot_setup.json` into `assets/`).
2. New scene, plain `Node3D` root, attach `demo_runtime.gd`, save, set as main scene.
3. Press **F5**.

Keys: **1** idle · **2** walk · **3** run · **4** slam · **5** bite · **6** take 8
damage (3rd hit kills at 22 hp) · **7** instant kill · **Q/E** turn · **R** respawn.

Confirm: states play, feet stay planted on the floor, attack hitboxes toggle only
inside their `hitbox_on`/`hitbox_off` windows. This is the **human-verified** gate.

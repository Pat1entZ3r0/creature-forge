## enemy_factory.gd — Godot 4.3+
##
## Builds a fully wired, playable enemy from two inputs:
##   1. a Node3D instantiated from the generated GLB (model + Skeleton3D + AnimationPlayer)
##   2. the parsed `*.godot_setup.json` sidecar dictionary produced by the pipeline
##
## Output node tree:
##   CharacterBody3D  (controller script attached, setup dict stored in meta "godot_setup")
##   ├─ Model                         (the GLB scene, reparented)
##   │   └─ ... Skeleton3D
##   │        ├─ HitboxMount_<id>     (BoneAttachment3D on the bone named in JSON)
##   │        │   └─ Hitbox_<id>      (Area3D, starts disabled; damage/tags in meta)
##   │        │       └─ CollisionShape3D (sphere from JSON radius/offset)
##   ├─ BodyCollision                 (CollisionShape3D capsule from JSON)
##   ├─ Hurtbox                       (Area3D capsule, monitorable so attacks can find it)
##   └─ AnimTree                      (AnimationTree, state machine built from JSON)
##
## HONESTY NOTE: this file was written carefully against the Godot 4.3 API but has
## NOT been executed inside a Godot editor in this environment (no engine available).
## Treat it as a strong first draft, not as CI-verified code.

class_name EnemyFactory
extends RefCounted


## Build the enemy. `model_scene` must already be instantiated (editor import or
## runtime GLTFDocument). `controller_script` is optional; pass
## preload("res://scripts/enemy_controller.gd") to get the playable controller.
static func build(model_scene: Node3D, setup: Dictionary, controller_script: Script = null) -> CharacterBody3D:
	var body := CharacterBody3D.new()
	body.name = String(setup.get("display_name", "Enemy")).replace(" ", "")

	# --- model ---------------------------------------------------------------
	model_scene.name = "Model"
	body.add_child(model_scene)

	var player: AnimationPlayer = _find_first(model_scene, "AnimationPlayer")
	var skeleton: Skeleton3D = _find_first(model_scene, "Skeleton3D")
	if player == null or skeleton == null:
		push_error("EnemyFactory: GLB scene is missing AnimationPlayer or Skeleton3D.")
		return body

	# --- loop modes (defensive) ----------------------------------------------
	# The "-loop" name suffix already drives Godot's importer, but when the GLB is
	# loaded at runtime, or if import settings were touched, this guarantees the
	# sidecar contract wins. Cheap and idempotent, so always do it.
	for a in setup.get("animations", []):
		var key := _resolve_anim_name(player, a["name"])
		if player.has_animation(key):
			var anim := player.get_animation(key)
			anim.loop_mode = Animation.LOOP_LINEAR if a.get("loop", false) else Animation.LOOP_NONE
		else:
			push_warning("EnemyFactory: animation '%s' listed in sidecar but absent from GLB." % a["name"])

	# --- body + hurt volumes ---------------------------------------------------
	if setup.has("collision"):
		body.add_child(_make_capsule_shape("BodyCollision", setup["collision"]))
	if setup.has("hurtbox"):
		var hurt := Area3D.new()
		hurt.name = "Hurtbox"
		hurt.monitoring = false   # it exists to BE found by attacks,
		hurt.monitorable = true   # not to scan for them
		hurt.add_to_group("enemy_hurtbox")
		hurt.add_child(_make_capsule_shape("HurtShape", setup["hurtbox"]))
		body.add_child(hurt)

	# --- bone-attached hitboxes -------------------------------------------------
	for hb in setup.get("hitboxes", []):
		var mount := BoneAttachment3D.new()
		mount.name = "HitboxMount_%s" % hb["id"]
		skeleton.add_child(mount)
		mount.bone_name = hb["bone"]

		var area := Area3D.new()
		area.name = "Hitbox_%s" % hb["id"]
		area.monitoring = false      # controller flips these on inside attack windows
		area.monitorable = false
		area.add_to_group("enemy_hitbox")
		area.set_meta("hitbox_id", hb["id"])
		area.set_meta("damage", hb.get("damage", 0))
		area.set_meta("tags", hb.get("tags", []))

		var cs := CollisionShape3D.new()
		cs.name = "Shape"
		if hb.get("shape", "sphere") == "sphere":
			var s := SphereShape3D.new()
			s.radius = hb["radius"]
			cs.shape = s
		else:
			push_warning("EnemyFactory: unsupported hitbox shape '%s', using sphere." % hb.get("shape"))
			var s2 := SphereShape3D.new()
			s2.radius = hb.get("radius", 0.1)
			cs.shape = s2
		cs.position = _v3(hb.get("offset", [0, 0, 0]))
		cs.disabled = true
		area.add_child(cs)
		mount.add_child(area)

	# --- animation tree / state machine ------------------------------------------
	var tree := AnimationTree.new()
	tree.name = "AnimTree"
	body.add_child(tree)
	tree.anim_player = tree.get_path_to(player)
	# Poll-based hitbox windows live in _physics_process, so keep the mixer in
	# physics time to make get_current_play_position() agree with the poller.
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	tree.tree_root = _build_state_machine(setup, player)
	tree.active = true

	# --- hand off to the controller ----------------------------------------------
	body.set_meta("godot_setup", setup)
	if controller_script != null:
		body.set_script(controller_script)
	return body


## Translate the sidecar's state_machine block into an AnimationNodeStateMachine.
## Transition rule derived from the contract:
##   * source animation loops            -> immediate, manually triggered edge
##   * source is one-shot, target "idle" -> AT_END + AUTO  (auto-return when done)
##   * everything else                   -> immediate, manually triggered edge
## Death is terminal: the sidecar gives it no outgoing edges, so a finished death
## clip simply holds its last pose.
static func _build_state_machine(setup: Dictionary, player: AnimationPlayer) -> AnimationNodeStateMachine:
	var sm := AnimationNodeStateMachine.new()
	var smd: Dictionary = setup.get("state_machine", {})
	var states: Dictionary = smd.get("states", {})

	var loops := {}
	for a in setup.get("animations", []):
		loops[a["name"]] = a.get("loop", false)

	# Lay states on a grid purely so the graph is readable if opened in-editor.
	var i := 0
	for state_name in states:
		var node := AnimationNodeAnimation.new()
		node.animation = _resolve_anim_name(player, states[state_name]["anim"])
		var pos := Vector2(200 + 240 * (i % 4), 100 + 160 * (i / 4))
		sm.add_node(state_name, node, pos)
		i += 1

	# Entry edge: Start -> declared start state, auto-advancing.
	var start_state: String = smd.get("start", "idle")
	if states.has(start_state):
		var st := AnimationNodeStateMachineTransition.new()
		st.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
		sm.add_transition("Start", start_state, st)

	for t in smd.get("transitions", []):
		var from: String = t[0]
		var to: String = t[1]
		var tr := AnimationNodeStateMachineTransition.new()
		tr.xfade_time = float(t[2])
		var from_anim: String = states.get(from, {}).get("anim", "")
		var from_loops: bool = loops.get(from_anim, true)
		if not from_loops and to == "idle":
			tr.switch_mode = AnimationNodeStateMachineTransition.SWITCH_MODE_AT_END
			tr.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
		sm.add_transition(from, to, tr)
	return sm


# ------------------------------------------------------------------ helpers ---

static func _make_capsule_shape(node_name: String, spec: Dictionary) -> CollisionShape3D:
	var cs := CollisionShape3D.new()
	cs.name = node_name
	var cap := CapsuleShape3D.new()
	cap.radius = spec.get("radius", 0.3)
	# Godot requires height >= 2*radius for a capsule; the sidecar's squat spider
	# capsule (h 0.62, r 0.34) is intentionally clamped here rather than silently
	# mutated by the engine.
	cap.height = max(float(spec.get("height", 0.6)), cap.radius * 2.0)
	cs.shape = cap
	cs.position = _v3(spec.get("offset", [0, 0, 0]))
	return cs


static func _resolve_anim_name(player: AnimationPlayer, anim_name: String) -> String:
	# Runtime GLTF loads and default editor imports both put clips in the unnamed
	# library, where the key is just the clip name. Fall back to a library scan in
	# case the asset was re-homed into a named AnimationLibrary.
	if player.has_animation(anim_name):
		return anim_name
	for lib_name in player.get_animation_library_list():
		var lib := player.get_animation_library(lib_name)
		if lib and lib.has_animation(anim_name):
			return anim_name if lib_name == &"" else "%s/%s" % [lib_name, anim_name]
	return anim_name


static func _find_first(root: Node, type_name: String) -> Node:
	var found := root.find_children("*", type_name, true, false)  # owned=false: runtime scenes have no owner
	return found[0] if found.size() > 0 else null


static func _v3(arr) -> Vector3:
	if arr is Array and arr.size() >= 3:
		return Vector3(arr[0], arr[1], arr[2])
	return Vector3.ZERO

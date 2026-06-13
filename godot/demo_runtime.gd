## demo_runtime.gd — Godot 4.3+
##
## Zero-asset smoke test. Attach to an empty Node3D, make that scene the project's
## main scene, drop spider_alien.glb + spider_alien.godot_setup.json into
## res://assets/, press F5. Everything else (floor, sun, sky, camera, UI) is
## constructed in code so the demo proves the whole runtime path:
##
##   GLB bytes -> GLTFDocument -> scene -> EnemyFactory.build() -> playable enemy
##
## Keys:  1 idle   2 walk   3 run   4 slam attack   5 lunge bite
##        6 take 8 damage (3rd hit kills: hp 22)     7 instant kill
##        Q / E turn        R reset position & respawn
##
## HONESTY NOTE: written against the Godot 4.3 API, not executed in-engine here.

extends Node3D

const EnemyFactoryScript := preload("res://scripts/enemy_factory.gd")
const EnemyControllerScript := preload("res://scripts/enemy_controller.gd")

@export var glb_path: String = "res://assets/spider_alien.glb"

var _enemy: CharacterBody3D
var _cam: Camera3D
var _status: Label


func _ready() -> void:
	_build_world()
	_spawn_enemy()


func _process(_delta: float) -> void:
	if _enemy and is_instance_valid(_enemy):
		# Simple chase cam: hover behind-right, look at the body.
		_cam.global_position = _enemy.global_position + Vector3(0.9, 0.8, 1.4)
		_cam.look_at(_enemy.global_position + Vector3(0, 0.2, 0))


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not _enemy:
		return
	var key := event as InputEventKey
	# Continuous turning on press/release.
	if key.keycode == KEY_Q:
		_enemy.set_turn(-1.0 if key.pressed else 0.0)
		return
	if key.keycode == KEY_E:
		_enemy.set_turn(1.0 if key.pressed else 0.0)
		return
	if not key.pressed or key.echo:
		return
	match key.keycode:
		KEY_1: _enemy.set_locomotion("idle")
		KEY_2: _enemy.set_locomotion("walk")
		KEY_3: _enemy.set_locomotion("run")
		KEY_4: _enemy.attack(1)
		KEY_5: _enemy.attack(2)
		KEY_6: _enemy.take_hit(8)
		KEY_7: _enemy.kill()
		KEY_R: _respawn()


# ----------------------------------------------------------------- world ---

func _build_world() -> void:
	var floor_body := StaticBody3D.new()
	floor_body.name = "Floor"
	var floor_shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(40, 0.1, 40)
	floor_shape.shape = box
	floor_body.add_child(floor_shape)
	var floor_mesh := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = box.size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.13, 0.13, 0.16)
	bm.material = mat
	floor_mesh.mesh = bm
	floor_body.add_child(floor_mesh)
	floor_body.position.y = -0.05  # top face sits exactly at y = 0, the contract's ground plane
	add_child(floor_body)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52, -30, 0)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	add_child(sun)

	var we := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.05, 0.08)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.45, 0.45, 0.55)
	env.ambient_light_energy = 0.8
	we.environment = env
	add_child(we)

	_cam = Camera3D.new()
	_cam.fov = 60
	add_child(_cam)

	var layer := CanvasLayer.new()
	_status = Label.new()
	_status.position = Vector2(12, 8)
	_status.add_theme_font_size_override("font_size", 15)
	layer.add_child(_status)
	add_child(layer)
	_set_status("spawning…")


# ----------------------------------------------------------------- enemy ---

func _spawn_enemy() -> void:
	var model := _load_glb_runtime(glb_path)
	if model == null:
		_set_status("FAILED to load %s — put the GLB in res://assets/" % glb_path)
		return

	var sidecar_path := glb_path.get_basename() + ".godot_setup.json"
	var setup = JSON.parse_string(FileAccess.get_file_as_string(sidecar_path))
	if not setup is Dictionary:
		_set_status("FAILED to parse sidecar %s" % sidecar_path)
		return

	_enemy = EnemyFactoryScript.build(model, setup, EnemyControllerScript)
	_enemy.position = Vector3(0, 0.02, 0)  # spawn a hair above the floor; gravity settles it
	add_child(_enemy)

	_enemy.state_changed.connect(func(s): _refresh_status("state: " + s))
	_enemy.damaged.connect(func(amt, hp): print("[demo] took %d damage, %d hp left" % [amt, hp]))
	_enemy.hit_landed.connect(func(target, id, dmg): print("[demo] hitbox '%s' struck %s for %d" % [id, target.name, dmg]))
	_enemy.died.connect(func(): print("[demo] death animation finished — corpse holds final pose"))
	_refresh_status("state: idle")


func _respawn() -> void:
	if _enemy and is_instance_valid(_enemy):
		_enemy.queue_free()
	_spawn_enemy()


func _load_glb_runtime(path: String) -> Node3D:
	# Deliberately use the runtime loader even for res:// files so this demo
	# exercises the no-editor path (modding / procedural spawning use case).
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(path, state) != OK:
		return null
	return doc.generate_scene(state) as Node3D


func _refresh_status(state_line: String) -> void:
	_set_status(state_line + "\n1 idle  2 walk  3 run  4 slam  5 bite  6 hit(8)  7 kill  Q/E turn  R respawn")


func _set_status(text: String) -> void:
	_status.text = text

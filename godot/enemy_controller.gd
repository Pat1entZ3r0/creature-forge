## enemy_controller.gd — Godot 4.3+
##
## Runtime brain for an enemy built by EnemyFactory. Everything gameplay-facing is
## read from the sidecar dict the factory stashed in meta "godot_setup":
##   * locomotion speeds come from the MEASURED values the validator wrote back
##     into the JSON (walk 0.216 m/s, run 0.532 m/s for the spider), so capsule
##     translation matches foot cadence with no foot-sliding tuning pass
##   * attack hitbox on/off windows come from animations[].events and are applied
##     by polling the state machine's play position each physics tick
##
## Public surface:
##   set_locomotion("idle"|"walk"|"run")
##   attack(1|2)            take_hit(amount)            kill()
##   set_turn(-1..1)        signals: state_changed, hit_landed, damaged, died
##
## HONESTY NOTE: written against the Godot 4.3 API, not executed in-engine here.

class_name EnemyController
extends CharacterBody3D

signal state_changed(state: String)
signal hit_landed(target: Node, hitbox_id: String, damage: int)
signal damaged(amount: int, health_left: int)
signal died

var setup: Dictionary = {}
var health: int = 1
var dead := false

var _tree: AnimationTree
var _playback: AnimationNodeStateMachinePlayback
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")

var _locomotion := "idle"        # desired ground state; attacks/hits interrupt it
var _turn_input := 0.0           # -1..1, scaled by sidecar turn_speed_dps
var _speed_by_state := {}        # "walk" -> 0.216 etc.
var _turn_speed_dps := 180.0

var _hitbox_areas := {}          # id -> Area3D
var _hitbox_active := {}         # id -> bool
var _windows_by_state := {}      # state name -> [{hitbox, t_on, t_off}]
var _last_state := ""


func _ready() -> void:
	setup = get_meta("godot_setup", {})
	health = int(setup.get("health", 1))

	_tree = get_node("AnimTree") as AnimationTree
	_playback = _tree.get("parameters/playback")
	_tree.animation_finished.connect(_on_animation_finished)

	var loco: Dictionary = setup.get("locomotion", {})
	_turn_speed_dps = float(loco.get("turn_speed_dps", 180.0))
	for key in ["walk", "run"]:
		if loco.has(key):
			_speed_by_state[key] = float(loco[key].get("speed_mps", 0.0))

	# Map hitbox event times (authored against animations) onto state names
	# (what the playback object reports), via the state -> anim table.
	var anim_windows := {}
	for a in setup.get("animations", []):
		if not a.has("events"):
			continue
		var open := {}
		var windows := []
		for ev in a["events"]:
			match ev.get("type", ""):
				"hitbox_on":
					open[ev["hitbox"]] = float(ev["t"])
				"hitbox_off":
					windows.append({
						"hitbox": ev["hitbox"],
						"t_on": float(open.get(ev["hitbox"], 0.0)),
						"t_off": float(ev["t"]),
					})
		anim_windows[a["name"]] = windows
	for state_name in setup.get("state_machine", {}).get("states", {}):
		var anim: String = setup["state_machine"]["states"][state_name]["anim"]
		if anim_windows.has(anim):
			_windows_by_state[state_name] = anim_windows[anim]

	for area: Area3D in find_children("Hitbox_*", "Area3D", true, false):
		var id := String(area.get_meta("hitbox_id", area.name))
		_hitbox_areas[id] = area
		_hitbox_active[id] = false
		area.body_entered.connect(_on_hitbox_body_entered.bind(id))
		area.area_entered.connect(_on_hitbox_area_entered.bind(id))


# --------------------------------------------------------------- public API ---

func set_locomotion(state: String) -> void:
	if dead or not state in ["idle", "walk", "run"]:
		return
	_locomotion = state
	_playback.travel(state)


func attack(index: int) -> void:
	if dead:
		return
	# travel() pathfinds along sidecar edges. From walk/run that path runs through
	# idle (walk->idle is an immediate edge), giving a brief blended settle before
	# the attack — acceptable for a POC; ship games add direct walk->attack edges.
	_playback.travel("attack_0%d" % index)


func take_hit(amount: int) -> void:
	if dead:
		return
	health -= amount
	damaged.emit(amount, health)
	if health <= 0:
		kill()
	else:
		# Note: no attack->hit edge exists in the sidecar, so a hit taken mid-attack
		# waits for the AT_END auto-return before reacting. Deliberate: the data
		# decides; add the edge in JSON if you want interruptible attacks.
		_playback.travel("hit")


func kill() -> void:
	if dead:
		return
	dead = true
	_locomotion = "idle"
	for id in _hitbox_areas:
		_set_hitbox(id, false)
	# Death must not queue behind an AT_END edge: take a direct edge if one exists
	# from the current state, otherwise teleport into the death state.
	var sm := _tree.tree_root as AnimationNodeStateMachine
	var cur := _playback.get_current_node()
	if sm and sm.has_transition(cur, "death"):
		_playback.travel("death")
	else:
		_playback.start("death")


func set_turn(dir: float) -> void:
	_turn_input = clampf(dir, -1.0, 1.0)


# ------------------------------------------------------------------ physics ---

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta

	var cur := String(_playback.get_current_node())
	if cur != _last_state:
		_last_state = cur
		state_changed.emit(cur)

	if dead:
		velocity.x = 0.0
		velocity.z = 0.0
	else:
		if absf(_turn_input) > 0.0:
			rotate_y(deg_to_rad(_turn_speed_dps) * -_turn_input * delta)
		# Drive the capsule only while the state machine is actually in a moving
		# state; clips are authored in place, so world speed lives entirely here.
		var speed: float = _speed_by_state.get(cur, 0.0)
		var fwd := -global_transform.basis.z  # model and Godot agree: forward is -Z
		velocity.x = fwd.x * speed
		velocity.z = fwd.z * speed

	move_and_slide()
	_update_hitboxes(cur)


func _update_hitboxes(cur: String) -> void:
	var pos := _playback.get_current_play_position()
	var want := {}
	for w in _windows_by_state.get(cur, []):
		if pos >= w["t_on"] and pos < w["t_off"]:
			want[w["hitbox"]] = true
	for id in _hitbox_areas:
		var on: bool = want.has(id)
		if on != _hitbox_active[id]:
			_set_hitbox(id, on)


func _set_hitbox(id: String, on: bool) -> void:
	_hitbox_active[id] = on
	var area: Area3D = _hitbox_areas[id]
	area.set_deferred("monitoring", on)
	var shape := area.get_node_or_null("Shape") as CollisionShape3D
	if shape:
		shape.set_deferred("disabled", not on)


# ------------------------------------------------------------------ signals ---

func _on_hitbox_body_entered(body: Node3D, id: String) -> void:
	if body == self:
		return
	var area: Area3D = _hitbox_areas[id]
	hit_landed.emit(body, id, int(area.get_meta("damage", 0)))


func _on_hitbox_area_entered(other: Area3D, id: String) -> void:
	if other.is_ancestor_of(self) or self.is_ancestor_of(other) or other.get_parent() == self:
		return
	if other.is_in_group("enemy_hitbox") or other.is_in_group("enemy_hurtbox"):
		return  # don't hit our own volumes
	var area: Area3D = _hitbox_areas[id]
	hit_landed.emit(other, id, int(area.get_meta("damage", 0)))


func _on_animation_finished(anim_name: StringName) -> void:
	if dead and String(anim_name).contains("death"):
		died.emit()

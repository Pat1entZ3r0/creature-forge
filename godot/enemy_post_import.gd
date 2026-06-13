## enemy_post_import.gd — Godot 4.3+
##
## Editor-side import hook. Assign this script under the GLB's Import dock:
##   select spider_alien.glb -> Import tab -> Import Script -> this file -> Reimport
##
## What it does at import time:
##   1. finds `<model>.godot_setup.json` sitting next to the source GLB
##   2. forces Animation.loop_mode to match the sidecar (belt-and-braces on top of
##      the "-loop" name suffix convention the importer already honors)
##   3. stores the parsed sidecar in the scene root's meta "godot_setup", so any
##      instantiation of the imported scene carries its gameplay contract with it
##
## This is the correct integration point named in the pipeline review:
## EditorScenePostImport (or a GLTFDocumentExtension for deeper surgery), NOT a
## from-scratch EditorImportPlugin — Godot already imports glTF perfectly well;
## we only annotate the result.
##
## HONESTY NOTE: written against the Godot 4.3 API, not executed in-engine here.

@tool
extends EditorScenePostImport


func _post_import(scene: Node) -> Object:
	var src := get_source_file()
	var sidecar_path := src.get_basename() + ".godot_setup.json"

	if not FileAccess.file_exists(sidecar_path):
		push_warning("enemy_post_import: no sidecar at '%s'; importing GLB untouched." % sidecar_path)
		return scene

	var raw := FileAccess.get_file_as_string(sidecar_path)
	var setup = JSON.parse_string(raw)
	if not setup is Dictionary:
		push_warning("enemy_post_import: sidecar '%s' is not valid JSON; importing untouched." % sidecar_path)
		return scene

	# Loop-mode enforcement from the contract.
	var players := scene.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		var player: AnimationPlayer = players[0]
		for a in setup.get("animations", []):
			var anim_name: String = a["name"]
			if player.has_animation(anim_name):
				var anim := player.get_animation(anim_name)
				anim.loop_mode = Animation.LOOP_LINEAR if a.get("loop", false) else Animation.LOOP_NONE
			else:
				push_warning("enemy_post_import: sidecar lists '%s' but the GLB has no such clip." % anim_name)

	scene.set_meta("godot_setup", setup)
	print("enemy_post_import: bound sidecar '%s' (%d animations, %d hitboxes)." % [
		sidecar_path.get_file(),
		setup.get("animations", []).size(),
		setup.get("hitboxes", []).size(),
	])
	return scene

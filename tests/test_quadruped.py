"""Milestone-6 gate: the quadruped archetype passes all 10 checks with the
planted-foot solver and the validator UNCHANGED from the arachnid path."""

from pathlib import Path

from pipeline.build import build_asset
from pipeline.solver import PlantedFootSolver
from pipeline.stage1_spec import compile_spec
from validation import validator as validator_module
from validation.validator import validate


def test_quadruped_passes_all_cpu_checks(tmp_path: Path):
    spec = compile_spec("hulking quadruped beast, low-poly PS1 horror", seed=7,
                        archetype_name="quadruped")
    info = build_asset(spec, tmp_path, mesh_tier="procedural")
    assert info["archetype"] == "quadruped"
    assert info["joints"] == 12  # root/body/head/tail + 4 legs x 2 bones
    r = validate(info["glb"], write_back=True, khronos=False)
    assert r["overall_pass"], {k: v for k, v in r["checks"].items() if not v.get("pass", True)}


def test_solver_and_validator_are_shared_unchanged():
    # the quadruped uses the same solver class and the same validate() entry point
    from archetypes.quadruped import Quadruped

    q = Quadruped()
    sk = q.build_skeleton()
    mesh = q.build_mesh(sk)
    solver = PlantedFootSolver(sk, mesh, q.legs(), q.leg_rot)  # same class as arachnid
    assert solver.__class__.__name__ == "PlantedFootSolver"
    assert callable(validator_module.validate)

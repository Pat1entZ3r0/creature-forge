"""Milestone-2 gate (as unit tests): the spider builds, validates 10/10, and is
byte-deterministic for a fixed seed."""

from pathlib import Path

from pipeline.build import build_asset
from pipeline.stage1_spec import compile_spec
from validation.validator import validate

PROMPT = "small venomous spider alien, low-poly PS1 horror style"


def test_spider_builds_and_passes_all_cpu_checks(tmp_path: Path):
    spec = compile_spec(PROMPT, seed=1337, archetype_name="arachnid")
    info = build_asset(spec, tmp_path, mesh_tier="procedural")
    assert info["triangles"] <= spec["tri_budget"]
    assert info["joints"] == 22
    assert set(info["clips"]) == {
        "idle-loop", "walk-loop", "run-loop", "attack_01", "attack_02", "hit", "death"
    }
    # khronos=False keeps the unit test node-free; Khronos 0/0/0/0 is covered by the run.
    r = validate(info["glb"], write_back=True, khronos=False)
    assert r["overall_pass"], {k: v for k, v in r["checks"].items() if not v.get("pass", True)}
    assert r["checks"]["foot_contact"]["worst_dev_mm"] <= 8.0
    assert r["checks"]["ground_penetration"]["worst_m"] >= -0.005


def test_build_is_byte_deterministic(tmp_path: Path):
    spec = compile_spec(PROMPT, seed=1337, archetype_name="arachnid")
    a = build_asset(spec, tmp_path / "a", mesh_tier="procedural")
    b = build_asset(spec, tmp_path / "b", mesh_tier="procedural")
    assert Path(a["glb"]).read_bytes() == Path(b["glb"]).read_bytes()

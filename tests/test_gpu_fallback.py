"""Milestone-4 gate (off-target): requesting the TRELLIS.2 tier without a green
preflight falls back to the procedural tier, records why, and still validates
10/10. On the AMD target with a green preflight the generative path runs instead."""

from pathlib import Path

from pipeline.build import build_asset
from pipeline.stage1_spec import compile_spec
from validation.validator import validate

PROMPT = "small venomous spider alien, low-poly PS1 horror style"


def test_trellis_tier_falls_back_offtarget(tmp_path: Path):
    spec = compile_spec(PROMPT, seed=1337, archetype_name="arachnid")
    info = build_asset(spec, tmp_path, mesh_tier="trellis")
    assert info["mesh_tier"] == "procedural"          # no GPU here -> fallback
    assert "fallback_reason" in info and "GPU" in info["fallback_reason"]
    r = validate(info["glb"], write_back=True, khronos=False)
    assert r["overall_pass"], r["checks"]


def test_gpu_modules_import_without_gpu():
    # importing the GPU stages must not require torch/trellis to be installed
    import pipeline.gpu.stage2_concept  # noqa: F401
    import pipeline.gpu.stage3_trellis  # noqa: F401
    import pipeline.gpu.stage4_finish  # noqa: F401
    import pipeline.gpu.stage5_fit  # noqa: F401
    from pipeline.gpu.availability import GpuUnavailable, gpu_enabled

    assert gpu_enabled() is False  # this build box is off-target
    assert issubclass(GpuUnavailable, RuntimeError)

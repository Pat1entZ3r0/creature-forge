"""Milestone-5 gate (as unit tests): caching, the seed-perturb iteration loop, and
the run manifest."""

from orchestrator.pipeline import run_pipeline

PROMPT = "small venomous spider alien, low-poly PS1 horror style"


def test_cold_then_warm_is_cache_hit():
    run_pipeline(PROMPT, 4242, "arachnid", use_cache=True, khronos=False, sheet=False)  # cold
    m = run_pipeline(PROMPT, 4242, "arachnid", use_cache=True, khronos=False, sheet=False)  # warm
    assert m["success"]
    assert m["attempts"][0]["cache_hit"] is True
    assert m["attempts"][0]["seconds"] < 0.5  # near-instant restore


def test_iteration_loop_recovers_after_forced_failures():
    m = run_pipeline(PROMPT, 1337, "arachnid", retries=3, use_cache=False,
                     khronos=False, sheet=False, fault_inject=2)
    assert m["success"]
    assert len(m["attempts"]) == 3
    assert m["attempts"][0]["gate"] == "INJECTED_FAILURE"
    assert m["attempts"][1]["seed"] != m["attempts"][0]["seed"]  # seed perturbed


def test_iteration_loop_exhausts_with_diagnosis():
    m = run_pipeline(PROMPT, 1337, "arachnid", retries=1, use_cache=False,
                     khronos=False, sheet=False, fault_inject=9)
    assert not m["success"]
    assert m["diagnosis"]["message"].startswith("gate failed")


def test_manifest_records_model_versions():
    m = run_pipeline(PROMPT, 5151, "arachnid", use_cache=False, khronos=False, sheet=False)
    assert m["model_versions"]["pipeline"]
    assert "total_seconds" in m

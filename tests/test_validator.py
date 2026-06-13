"""Milestone-1 gate: the validator PASSES a good fixture and FAILS a broken one."""

from tests.fixture import build_all
from validation.validator import validate


def test_good_fixture_passes_all_cpu_checks():
    good, _ = build_all()
    # khronos=False keeps the unit test free of the node dependency; the full
    # 10/10 incl. Khronos 0/0/0/0 is exercised by the validator CLI and M2 gate.
    r = validate(good, write_back=False, khronos=False)
    assert r["overall_pass"], r["checks"]
    for name, chk in r["checks"].items():
        assert chk.get("pass", True), (name, chk)


def test_broken_fixture_fails_ground_penetration():
    _, broken = build_all()
    r = validate(broken, write_back=False, khronos=False)
    assert not r["overall_pass"]
    assert r["checks"]["ground_penetration"]["pass"] is False
    assert r["checks"]["ground_penetration"]["worst_m"] <= -0.05


def test_schemas_validate():
    from validation.schema_check import validate_examples

    assert len(validate_examples()) == 2

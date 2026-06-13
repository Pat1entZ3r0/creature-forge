"""
orchestrator/pipeline.py — the run engine: caching, iteration loop, manifest.

- Content-hash cache: each run's artifacts are keyed on the hash of (spec + seed +
  mesh tier + model/pipeline version). An identical rerun restores from cache and
  skips build + validation (near-instant).
- Iteration loop: when the validator gate fails, the run regenerates with a
  perturbed seed up to N times before failing with a clear per-check diagnosis.
- Manifest: every run writes out/run_manifest.json (attempts, seeds, model
  versions, gate results, timings, cache hits) so any asset is reproducible.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import tomllib
from pathlib import Path

from pipeline.build import build_asset
from pipeline.stage1_spec import compile_spec
from validation.validator import validate

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
CACHE = OUT / ".cache"
CONFIG = ROOT / "config" / "pipeline.toml"
PIPELINE_VERSION = "0.1.0"

_ARTIFACTS = ["{stem}.glb", "{stem}.asset_spec.json", "{stem}.godot_setup.json"]


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def _model_versions(mesh_tier: str) -> dict:
    models = _config().get("models", {})
    out = {"pipeline": PIPELINE_VERSION, "mesh_tier": mesh_tier}
    if mesh_tier == "trellis":
        out["trellis2"] = models.get("trellis2", {}).get("rev", "unknown")
    return out


def cache_key(spec: dict, mesh_tier: str) -> str:
    blob = json.dumps(spec, sort_keys=True) + f"|tier={mesh_tier}|v={PIPELINE_VERSION}"
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _perturb(seed: int, attempt: int) -> int:
    return seed + attempt * 7919  # deterministic seed perturbation on gate failure


def _restore_from_cache(key: str, stem: str) -> dict | None:
    cdir = CACHE / key
    report = cdir / "validation_report.json"
    if not report.exists():
        return None
    OUT.mkdir(parents=True, exist_ok=True)
    for tmpl in _ARTIFACTS + ["validation_report.json", "qa_contact_sheet.png"]:
        name = tmpl.format(stem=stem)
        src = cdir / name
        if src.exists():
            shutil.copy2(src, OUT / name)
    return json.loads(report.read_text(encoding="utf-8"))


def _store_to_cache(key: str, stem: str) -> None:
    cdir = CACHE / key
    cdir.mkdir(parents=True, exist_ok=True)
    for tmpl in _ARTIFACTS + ["validation_report.json", "qa_contact_sheet.png"]:
        name = tmpl.format(stem=stem)
        src = OUT / name
        if src.exists():
            shutil.copy2(src, cdir / name)


def _failing_checks(report: dict) -> dict:
    return {k: v for k, v in report.get("checks", {}).items() if not v.get("pass", True)}


def run_pipeline(prompt: str, seed: int, archetype: str, mesh_tier: str = "procedural",
                 retries: int = 3, use_cache: bool = True, khronos: bool = True,
                 sheet: bool = True, fault_inject: int = 0) -> dict:
    """Execute the gated pipeline with caching + the seed-perturb iteration loop."""
    t0 = time.perf_counter()
    attempts = []
    manifest = {
        "prompt": prompt, "archetype": archetype, "mesh_tier_requested": mesh_tier,
        "model_versions": _model_versions(mesh_tier), "attempts": attempts,
    }
    final_report = None
    success = False

    for attempt in range(retries + 1):
        eff_seed = seed if attempt == 0 else _perturb(seed, attempt)
        a_t = time.perf_counter()
        spec = compile_spec(prompt, eff_seed, archetype)
        key = cache_key(spec, mesh_tier)
        stem = None
        rec = {"attempt": attempt, "seed": eff_seed, "cache_key": key}

        # cache restore
        if use_cache and not (fault_inject and attempt < fault_inject):
            # discover stem from a cached spec if present (archetype model_stem)
            from pipeline.registry import get_archetype

            stem = get_archetype(archetype).model_stem
            cached = _restore_from_cache(key, stem)
            if cached is not None:
                rec.update(cache_hit=True, overall_pass=cached["overall_pass"],
                           seconds=round(time.perf_counter() - a_t, 4))
                attempts.append(rec)
                final_report = cached
                success = cached["overall_pass"]
                if success:
                    break
                continue

        # build + validate
        info = build_asset(spec, OUT, mesh_tier=mesh_tier)
        stem = info["stem"]
        rec["mesh_tier_used"] = info["mesh_tier"]
        if info.get("fallback_reason"):
            rec["fallback_reason"] = info["fallback_reason"]

        if fault_inject and attempt < fault_inject:
            rec.update(cache_hit=False, gate="INJECTED_FAILURE",
                       seconds=round(time.perf_counter() - a_t, 4))
            attempts.append(rec)
            continue

        report = validate(info["glb"], write_back=True, khronos=khronos)
        OUT.joinpath("validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if sheet:
            try:
                from validation.contact_sheet import render

                render(info["glb"], OUT / "qa_contact_sheet.png")
            except Exception:  # noqa: BLE001
                pass

        rec.update(cache_hit=False, overall_pass=report["overall_pass"],
                   failing=list(_failing_checks(report)),
                   seconds=round(time.perf_counter() - a_t, 4))
        attempts.append(rec)
        final_report = report
        if report["overall_pass"]:
            _store_to_cache(key, stem)
            success = True
            break

    manifest.update(
        success=success,
        total_seconds=round(time.perf_counter() - t0, 4),
        diagnosis=None if success else
        {"message": f"gate failed after {len(attempts)} attempt(s)",
         "last_failing_checks": _failing_checks(final_report or {})},
    )
    OUT.mkdir(parents=True, exist_ok=True)
    OUT.joinpath("run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

"""
orchestrator/cli.py — `pipeline run`.

  pipeline run --prompt "..." --seed 1337 --archetype arachnid --mesh-tier auto

Drives the run engine (orchestrator/pipeline.py): content-hash cache, seed-perturb
iteration loop on gate failure, and a per-run manifest. mesh-tier `auto` reads
out/preflight.json — `trellis` only when the GPU preflight is green, else procedural.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
CONFIG = ROOT / "config" / "pipeline.toml"


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def _resolve_mesh_tier(requested: str) -> str:
    if requested != "auto":
        return requested
    pf = OUT / "preflight.json"
    if pf.exists():
        try:
            if json.loads(pf.read_text()).get("gpu_enabled"):
                return "trellis"
        except Exception:  # noqa: BLE001
            pass
    return "procedural"


def run(args) -> int:
    from orchestrator.pipeline import run_pipeline

    cfg = _config().get("run", {})
    prompt = args.prompt or cfg.get("default_prompt")
    seed = args.seed if args.seed is not None else cfg.get("default_seed", 1337)
    archetype = args.archetype or cfg.get("default_archetype", "arachnid")
    tier = _resolve_mesh_tier(args.mesh_tier or cfg.get("mesh_tier", "auto"))
    retries = args.retries if args.retries is not None else cfg.get("iteration_retries", 3)

    print(f"pipeline run  prompt={prompt!r}  seed={seed}  archetype={archetype}  "
          f"mesh_tier={tier}  retries={retries}")
    m = run_pipeline(prompt, seed, archetype, mesh_tier=tier, retries=retries,
                     use_cache=not args.no_cache, khronos=not args.no_khronos,
                     sheet=not args.no_sheet, fault_inject=args.fault_inject)

    for a in m["attempts"]:
        tag = ("CACHE HIT" if a.get("cache_hit") else
               a.get("gate") or ("PASS" if a.get("overall_pass") else "FAIL"))
        extra = f" failing={a['failing']}" if a.get("failing") else ""
        if a.get("fallback_reason"):
            extra += f" (fallback: {a['fallback_reason'].split(' - ')[0]})"
        print(f"  attempt {a['attempt']}  seed={a['seed']}  {a['seconds']}s  -> {tag}{extra}")

    print(f"\nmanifest: out/run_manifest.json   total {m['total_seconds']}s")
    if m["success"]:
        print("RUN: PASS")
        return 0
    print(f"RUN: FAIL - {m['diagnosis']['message']}")
    print(f"  last failing checks: {list(m['diagnosis']['last_failing_checks'])}")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    p = argparse.ArgumentParser(prog="pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="generate a validated asset from a prompt")
    r.add_argument("--prompt")
    r.add_argument("--seed", type=int)
    r.add_argument("--archetype")
    r.add_argument("--mesh-tier", dest="mesh_tier", default=None,
                   choices=["auto", "procedural", "trellis"])
    r.add_argument("--retries", type=int, default=None)
    r.add_argument("--no-cache", action="store_true")
    r.add_argument("--no-khronos", action="store_true")
    r.add_argument("--no-sheet", action="store_true")
    r.add_argument("--fault-inject", dest="fault_inject", type=int, default=0,
                   help="force the first N attempts to fail (demonstrates the retry loop)")
    args = p.parse_args(argv)
    if args.cmd == "run":
        return run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())

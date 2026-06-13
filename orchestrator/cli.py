"""
orchestrator/cli.py — `pipeline run`.

Milestone 2 wiring: compile spec -> build (Stages 5/3/6/7) -> validate (Stage 8,
with measured-speed write-back) -> QA contact sheet. The content-hash cache,
seed-perturb iteration loop and run manifest are layered on in Milestone 5.
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
    """auto -> read out/preflight.json; GPU stages need a green preflight."""
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
    from pipeline.build import build_asset
    from pipeline.stage1_spec import compile_spec
    from validation.validator import validate

    cfg = _config().get("run", {})
    prompt = args.prompt or cfg.get("default_prompt")
    seed = args.seed if args.seed is not None else cfg.get("default_seed", 1337)
    archetype = args.archetype or cfg.get("default_archetype", "arachnid")
    tier = _resolve_mesh_tier(args.mesh_tier or cfg.get("mesh_tier", "auto"))
    if tier == "trellis":
        print("mesh-tier: trellis (GPU) requested — see Milestone 4. Falling back to procedural here.")
        tier = "procedural"

    print(f"Stage 1: compiling spec  prompt={prompt!r}  seed={seed}  archetype={archetype}")
    spec = compile_spec(prompt, seed, archetype)

    print(f"Stages 3/5/6/7: building asset (mesh_tier={tier}) ...")
    info = build_asset(spec, OUT, mesh_tier=tier)
    print(f"  -> {info['glb'].name}  {info['bytes']} bytes  {info['triangles']} tris  "
          f"{info['vertices']} verts  {info['joints']} joints  clips={info['clips']}")

    print("Stage 8: validating + measuring speeds ...")
    report = validate(info["glb"], write_back=True, khronos=not args.no_khronos)
    (OUT / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    passed = sum(1 for c in report["checks"].values() if c.get("pass"))
    print(f"  -> {passed}/{len(report['checks'])} checks, overall_pass={report['overall_pass']}")
    if report["warnings"]:
        for w in report["warnings"]:
            print(f"  ! {w}")

    if not args.no_sheet:
        try:
            from validation.contact_sheet import render

            png = render(info["glb"], OUT / "qa_contact_sheet.png")
            print(f"QA contact sheet: {png.name}")
        except Exception as e:  # noqa: BLE001
            print(f"  (contact sheet skipped: {e})")

    print("\nRUN:", "PASS" if report["overall_pass"] else "FAIL")
    return 0 if report["overall_pass"] else 1


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
    r.add_argument("--no-khronos", action="store_true")
    r.add_argument("--no-sheet", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "run":
        return run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())

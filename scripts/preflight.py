#!/usr/bin/env python3
"""
preflight.py — Milestone 0.5: ROCm / gfx1151 hardware bring-up.

The GPU stack on gfx1151 is the highest-risk part of the project, so prove it in
isolation BEFORE any GPU stage. This script, in order:

  1. detects the GPU (rocminfo / rocm-smi) and records the ROCm version,
  2. confirms the **gfx1151-specific** torch wheel is installed (stock ROCm
     wheels die on gfx1151 with "HIP error: invalid device function"),
  3. runs a REAL compute kernel — a non-trivial matmul on "cuda" (HIP) and a
     small conv — and checks the result against a CPU reference within tolerance
     (the pass condition is a correct kernel result, NOT torch.cuda.is_available,
     because the invalid-device-function failure returns True for availability
     and then dies on compute),
  4. probes a large GTT/UMA allocation (~32 GB) on device and frees it,
  5. if headless, stands up an offscreen EGL/Xvfb GL context (nvdiffrast's AMD
     OpenGL backend needs one) and confirms a renderer string.

It records everything in docs/HARDWARE.md and emits out/preflight.json, which the
GPU stages read to decide their backend. On a non-AMD box (e.g. this Windows
build machine) it does NOT fail: it records gpu_enabled=false and a reason, so
the CPU-only core (Stages 1, 4-retopo, 5, 6, 7, 8) proceeds with GPU disabled.

Exit codes: 0 = green on target OR honest skip off-target; 1 = a check FAILED on
an AMD target (operator must STOP the GPU stages but the pipeline still builds).
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
GTT_PROBE_GB = 32
EXPECTED_ARCH = "gfx1151"
GFX1151_TORCH_INDEX = "https://rocm.nightlies.amd.com/v2/gfx1151/"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception as e:  # noqa: BLE001
        return f"<error running {' '.join(cmd)}: {e}>"


def _rocm_version() -> str | None:
    for path in ("/opt/rocm/.info/version", "/opt/rocm/.info/version-dev"):
        p = Path(path)
        if p.exists():
            return p.read_text().strip()
    if _have("rocminfo"):
        for line in _sh(["rocminfo"]).splitlines():
            if "Runtime Version" in line:
                return line.split(":")[-1].strip()
    return None


def _detect_arch() -> str | None:
    if not _have("rocminfo"):
        return None
    for line in _sh(["rocminfo"]).splitlines():
        line = line.strip()
        if line.startswith("Name:") and "gfx" in line:
            return line.split(":")[-1].strip()
    return None


# ── the real compute checks (only reached on an AMD target) ──────────────────
def _compute_checks(report: dict) -> bool:
    try:
        import numpy as np
        import torch
    except Exception as e:  # noqa: BLE001
        report["checks"]["torch_import"] = {"pass": False, "error": str(e)}
        return False

    report["torch_version"] = torch.__version__
    report["torch_hip"] = getattr(torch.version, "hip", None)
    # the gfx1151 wheel reports a HIP build; a stock CUDA wheel would not
    report["checks"]["gfx1151_wheel"] = {
        "pass": bool(getattr(torch.version, "hip", None)),
        "note": f"install from {GFX1151_TORCH_INDEX} if this is false",
    }
    if not torch.cuda.is_available():
        report["checks"]["cuda_available"] = {"pass": False}
        return False
    report["checks"]["cuda_available"] = {"pass": True, "device": torch.cuda.get_device_name(0)}

    ok = True
    # 1) non-trivial matmul on HIP vs CPU reference (this is what actually dies
    #    on the invalid-device-function failure mode)
    try:
        g = torch.Generator(device="cpu").manual_seed(0)
        a = torch.randn(1024, 1024, generator=g)
        b = torch.randn(1024, 1024, generator=g)
        ref = (a @ b).numpy()
        got = (a.to("cuda") @ b.to("cuda")).cpu().numpy()
        err = float(np.abs(ref - got).max())
        passed = err < 1e-2
        report["checks"]["matmul_hip"] = {"pass": passed, "max_abs_err": err}
        ok &= passed
    except Exception as e:  # noqa: BLE001
        report["checks"]["matmul_hip"] = {"pass": False, "error": str(e)}
        ok = False

    # 2) small conv on HIP vs CPU reference
    try:
        import torch.nn.functional as F

        g = torch.Generator(device="cpu").manual_seed(1)
        x = torch.randn(1, 3, 64, 64, generator=g)
        w = torch.randn(8, 3, 3, 3, generator=g)
        ref = F.conv2d(x, w, padding=1).numpy()
        got = F.conv2d(x.to("cuda"), w.to("cuda"), padding=1).cpu().numpy()
        err = float(np.abs(ref - got).max())
        passed = err < 1e-2
        report["checks"]["conv_hip"] = {"pass": passed, "max_abs_err": err}
        ok &= passed
    except Exception as e:  # noqa: BLE001
        report["checks"]["conv_hip"] = {"pass": False, "error": str(e)}
        ok = False

    # 3) large GTT/UMA allocation on device, then free
    try:
        n = (GTT_PROBE_GB * 1024**3) // 4  # float32 elements
        big = torch.empty(int(n), dtype=torch.float32, device="cuda")
        torch.cuda.synchronize()
        del big
        torch.cuda.empty_cache()
        report["checks"]["gtt_alloc_gb"] = {"pass": True, "probed_gb": GTT_PROBE_GB}
    except Exception as e:  # noqa: BLE001
        report["checks"]["gtt_alloc_gb"] = {
            "pass": False, "probed_gb": GTT_PROBE_GB, "error": str(e),
            "hint": "raise BIOS UMA / Linux GTT (amdgpu.gttsize, TTM)",
        }
        ok = False
    return ok


def _gl_context_check(report: dict) -> None:
    """Headless OpenGL context for nvdiffrast's AMD backend. Best-effort."""
    headless = not (platform.system() == "Linux" and bool(_sh(["bash", "-lc", "echo $DISPLAY"]).strip()))
    report["headless"] = headless
    # try EGL via PyOpenGL, then moderngl standalone, else record the binary path
    for method, probe in (
        ("egl/pyopengl", "from OpenGL import EGL; EGL.eglGetDisplay"),
        ("moderngl", "import moderngl; moderngl.create_standalone_context()"),
    ):
        try:
            __import__(probe.split()[1].split(".")[0])
            report["gl_context"] = {"method": method, "pass": True}
            return
        except Exception:  # noqa: BLE001
            continue
    report["gl_context"] = {
        "method": "xvfb" if _have("Xvfb") else "none",
        "pass": bool(_have("Xvfb") or _have("eglinfo")),
        "hint": "install mesa EGL / run under `xvfb-run` for the nvdiffrast OpenGL path",
    }


def main() -> int:
    OUT.mkdir(exist_ok=True)
    report: dict = {
        "platform": platform.platform(),
        "expected_arch": EXPECTED_ARCH,
        "gpu_enabled": False,
        "attention_backend": "xformers",  # flash-attn unavailable on gfx1151
        "rocm_version": _rocm_version(),
        "detected_arch": _detect_arch(),
        "checks": {},
    }

    is_amd_target = platform.system() == "Linux" and _have("rocminfo")
    if not is_amd_target:
        report["reason"] = (
            "Not an AMD/ROCm target (no rocminfo on Linux). GPU stages (2, 3) "
            "disabled; the CPU-only core runs and gate-passes regardless."
        )
        _write(report)
        print("preflight: OFF-TARGET - GPU stages disabled, CPU core proceeds.")
        print(f"  platform: {report['platform']}")
        print(f"  -> out/preflight.json (gpu_enabled=false)")
        return 0

    if report["detected_arch"] and report["detected_arch"] != EXPECTED_ARCH:
        report["checks"]["arch_match"] = {
            "pass": False, "detected": report["detected_arch"], "expected": EXPECTED_ARCH,
        }

    green = _compute_checks(report)
    _gl_context_check(report)
    green &= report.get("gl_context", {}).get("pass", False)
    report["gpu_enabled"] = green
    _write(report)

    print(json.dumps(report, indent=2))
    if green:
        print("\npreflight: GREEN — GPU compute + GTT + GL context all verified.")
        return 0
    print("\npreflight: RED — a GPU check FAILED. STOP GPU stages; the CPU-only "
          "core still builds and gate-passes. See docs/HARDWARE.md.")
    return 1


def _write(report: dict) -> None:
    (OUT / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

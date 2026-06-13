# Hardware & ROCm bring-up (gfx1151)

Target: **AMD Ryzen AI Max+ 395 "Strix Halo"** — 16 Zen 5 cores, integrated
**Radeon 8060S (RDNA 3.5, 40 CU, `gfx1151`)**, XDNA 2 NPU, **128 GB unified
LPDDR5x** (~96 GB addressable by the iGPU), Ubuntu 24.04, ROCm 7.x. No CUDA, no
discrete GPU. The compute strategy follows from these facts:

- **GPU compute is ROCm/HIP, not CUDA.** PyTorch's ROCm build exposes everything
  through the `torch.cuda.*` API (so `.to("cuda")` is correct and portable), but
  the runtime is HIP. No `nvidia-smi` / `nvcc`; no CUDA-only kernels.
- **`gfx1151` is unlisted on AMD's official support matrix** (listed RDNA3 is
  gfx1100/1101) but works. **Stock PyTorch ROCm wheels FAIL on gfx1151 with
  `HIP error: invalid device function`.** Install AMD's gfx1151-specific wheels:

  ```bash
  python3.12 -m venv .venv && . .venv/bin/activate
  pip install --index-url https://rocm.nightlies.amd.com/v2/gfx1151/ --pre \
      torch torchvision torchaudio
  ```

  Installing other packages can silently clobber this with a CUDA wheel — pin it
  and re-verify after every environment change.
- **The constraint is bandwidth (~256 GB/s) and 40-CU throughput, not VRAM.**
  TRELLIS.2-4B and FLUX fit without quantization; generation is **minutes, not
  seconds** — fine for an offline asset pipeline. Don't spend effort on
  8–24 GB VRAM-saving tricks; spend it on throughput.
- **flash-attn, bitsandbytes, torchao do not work on gfx1151.** Use
  xformers / PyTorch-native attention (`ATTN_BACKEND=xformers`).
- **Unified memory** is enabled via BIOS UMA + Linux GTT (`amdgpu.gttsize`, TTM).
  The preflight probes a 32 GB device allocation to confirm.
- **Headless GL:** nvdiffrast's AMD path uses its **OpenGL backend** and needs a
  live GL context — provide **EGL/GBM** or run under **`xvfb-run`**.

## The preflight (`scripts/preflight.py`)

Run it before any GPU stage:

```bash
python scripts/preflight.py        # -> out/preflight.json
```

It detects the GPU and ROCm version, confirms the gfx1151 torch wheel
(`torch.version.hip` set), runs a **real** matmul + conv on `"cuda"` and checks
them against a CPU reference (a correct kernel result is the pass condition — not
`torch.cuda.is_available()`, which returns True even in the invalid-device-
function failure), probes a 32 GB GTT allocation, and stands up an offscreen GL
context if headless. It writes `out/preflight.json`; the GPU stages read
`gpu_enabled` from it to choose their backend.

- **Green on target** → GPU stages (2, 3) may run; TRELLIS.2 becomes the default
  mesh tier (Milestone 4).
- **Red on target** → STOP the GPU stages, record the exact failure here, and the
  pipeline continues on the deterministic **procedural Stage-3 fallback**. Every
  CPU gate still passes.

## Recorded environment (fill in from a real run on the target)

| Field | Value |
|-------|-------|
| ROCm version | _(preflight: `rocm_version`)_ |
| torch wheel | _(preflight: `torch_version` / `torch_hip`)_ |
| detected arch | _(preflight: `detected_arch`, expect `gfx1151`)_ |
| GTT probe | _(preflight: `gtt_alloc_gb`, 32 GB)_ |
| attention backend | xformers |
| GL context method | _(preflight: `gl_context.method`)_ |

> This was built on a **Windows 11** box with no ROCm. `preflight.py` there
> records `gpu_enabled=false` with a reason and exits 0 — an honest off-target
> skip, not a failure. The values above are placeholders until the preflight is
> run on the Strix Halo target.

# Run dashboard

A local operator view of a pipeline run — the live GLB, the 10-check validation
ledger, the measured locomotion speeds, the run manifest (cache hits, retries,
timings), and the QA contact sheet. Vite + React + `@google/model-viewer`, in the
same forensic-lab aesthetic as the rest of the project.

```bash
# from repo root: generate a run first
make run

cd dashboard
npm install
npm run dev        # syncs out/ -> public/data, then serves at http://localhost:5173
npm run build      # static bundle in dashboard/dist
```

`sync.mjs` copies the current `out/` artifacts into `public/data/` so the app can
fetch them over http. A snapshot is committed so the dashboard renders on a fresh
clone without running the pipeline; `npm run sync` refreshes it after a new run.

Pushing to `main` builds and deploys the dashboard (against the committed snapshot)
to GitHub Pages via `.github/workflows/deploy-dashboard.yml`.

// Copy the pipeline's out/ artifacts into public/data so the dashboard can fetch
// them over http. Run before `vite`/`build` (npm run dev does it automatically).
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "out");
const data = join(here, "public", "data");
mkdirSync(data, { recursive: true });

const files = [
  "validation_report.json",
  "run_manifest.json",
  "qa_contact_sheet.png",
  "spider_alien.glb",
  "spider_alien.asset_spec.json",
  "spider_alien.godot_setup.json",
];

let copied = 0;
for (const f of files) {
  const src = join(out, f);
  if (existsSync(src)) {
    cpSync(src, join(data, f));
    copied++;
  }
}
console.log(`sync: ${copied}/${files.length} artifacts -> public/data (run \`make run\` first if 0)`);
